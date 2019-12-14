#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import sqlite3
import copy
import urllib
from http.server import HTTPServer, BaseHTTPRequestHandler


# In[2]:


def read_data():
    conn = sqlite3.connect('mydb.sqlite')

    df = pd.read_sql_query("SELECT * FROM Smenas", conn)
    df.when = df.when.apply(pd.to_datetime,yearfirst=True)
    conn.close()
    return df


# In[3]:


def count_deltas(df):


    new_df = df.groupby(['morning','who']).count().reset_index()

    morning_m = new_df[new_df.morning.eq(1)&new_df.who.eq('M')].when.values[0]
    morning_p = new_df[new_df.morning.eq(1)&new_df.who.eq('P')].when.values[0]
    evening_m = new_df[new_df.morning.eq(0)&new_df.who.eq('M')].when.values[0]
    evening_p = new_df[new_df.morning.eq(0)&new_df.who.eq('P')].when.values[0]

    delta_morning = morning_m - morning_p
    delta_evening = evening_m - evening_p
    
    return delta_morning,delta_evening


# In[4]:


def get_last_7_day_history(df):
    last_day = df.when.max()
    target_history = df[(last_day - df.when).dt.days < 7]
    target_history = target_history.sort_values(['when','morning'],ascending=[True,False])
    return target_history


# In[5]:


def generage_suggestion(df):
    delta_morning,delta_evening = count_deltas(df)    

    last = df.sort_values(['when','morning'],ascending=[True,False]).iloc[-1]
    current = copy.copy(last)

    suggestions = []
    while True:
        if current.morning==0:
            current.morning=1
            current.when += pd.Timedelta('1d')
        else:
            current.morning=0
        if (current.when - last.when).days >6:
            break
        if current.morning==1:
            if delta_morning>0:
                current.who = 'P'
                delta_morning -=1
            else:
                current.who = 'M'
                delta_morning +=1
        else:
            if delta_evening>0:
                current.who = 'P'
                delta_evening -=1
            else:
                current.who = 'M'
                delta_evening +=1
        suggest = copy.copy(current)
        suggestions.append(suggest)

    return pd.DataFrame.from_records(suggestions)


# In[6]:


df = read_data()


# In[7]:


generage_suggestion(df)


# In[8]:


template='''<html>
<meta charset="utf-8" /> 
<style>
table, th, td {{
  border: 1px solid black;
}}

.done {{
	background-color: Chartreuse;
}}

.suggest {{
	background-color: Aqua;
}}
</style>
History<br>
{history_table}
<br>
Now <br>
morning {morning_delta}<br>
evening {evening_delta}<br>
0 - очередь Маши<br>
1 - очередь Паши<br>
<br><br>
Input<br>
<form method=POST>
{input_table}
<br>
<input type=submit value="Отправить">
</form>


</html>'''


# In[9]:


table_template = '''<table>

<tr>
	<th> Кто </th>
    {dates}
</tr>
<tr>
	<td></td>
    {mornings}
</tr>
<tr>
	<td>П</td>
    {pavel}
</tr>
<tr>
	<td>М</td>
    {maria}
</tr>
</table>'''

def generate_history_table(df):
    delta_morning,delta_evening = count_deltas(df)

    history_to_show = get_last_7_day_history(df)
    suggestions = generage_suggestion(df)

    history_to_show['is_suggestion']=False
    suggestions['is_suggestion'] = True
    df_to_show = pd.concat([history_to_show,suggestions])

    dates_to_show = df_to_show.when[::2]
    dates_to_show = dates_to_show.dt.strftime('%d-%m-%y') +'<br>'+ dates_to_show.dt.dayofweek.apply(lambda x: day_of_week[x])
    dates_to_show = '<th colspan="2">'+dates_to_show+ '</th>'
    dates_string = '\n'.join(dates_to_show)

    mornings = '''	<td>У</td>
        <td>В</td>
    '''*len(dates_to_show)

    done = '	<td class="done">+</td>'
    suggest = '	<td class="suggest">+</td>'
    not_done = '	<td></td>'

    pavel_string = '\n'.join(df_to_show.apply(lambda x: (suggest if x.is_suggestion else done) if x.who=='P' else not_done,axis=1))
    maria_string = '\n'.join(df_to_show.apply(lambda x: (suggest if x.is_suggestion else done) if x.who=='M' else not_done,axis=1))

    response = table_template.format(dates=dates_string,mornings=mornings,
                    pavel=pavel_string,maria=maria_string)
    return response


def generate_input_table(df):
    delta_morning,delta_evening = count_deltas(df)

    history_to_show = get_last_7_day_history(df)
    suggestions = generage_suggestion(df)

    history_to_show['is_suggestion']=False
    suggestions['is_suggestion'] = True
    df_to_show = pd.concat([history_to_show,suggestions])

    dates_to_show = df_to_show.when[::2]
    dates_to_show = dates_to_show.dt.strftime('%d-%m-%y') +'<br>'+ dates_to_show.dt.dayofweek.apply(lambda x: day_of_week[x])
    dates_to_show = '<th colspan="2">'+dates_to_show+ '</th>'
    dates_string = '\n'.join(dates_to_show)

    mornings = '''	<td>У</td>
        <td>В</td>
    '''*len(dates_to_show)

    done = '	<td class="done">+</td>'
    suggest = '	<td class="suggest">+</td>'
    not_done = '	<td></td>'

    pavel_string = '\n'.join(history_to_show.apply(lambda x: (suggest if x.is_suggestion else done) if x.who=='P' else not_done,axis=1))
    maria_string = '\n'.join(history_to_show.apply(lambda x: (suggest if x.is_suggestion else done) if x.who=='M' else not_done,axis=1))
    
    input_format = '<td class="suggest"><input type=checkbox name="{who}|{date}|{morning}"></td>'
    pavel_string2 = '\n'.join(suggestions.apply(lambda x: input_format.format(who='P',
                                                                        date=x.when.strftime('%Y-%m-%d'),
                                                                        morning=x.morning)
                                          , axis=1))
    maria_string2 = '\n'.join(suggestions.apply(lambda x: input_format.format(who='M',
                                                                        date=x.when.strftime('%Y-%m-%d'),
                                                                        morning=x.morning)
                                          , axis=1))
    pavel_string += '\n' + pavel_string2
    maria_string += '\n' + maria_string2
    response = table_template.format(dates=dates_string,mornings=mornings,
                    pavel=pavel_string,maria=maria_string)
    return response


# In[10]:


day_of_week = ['пнд','вт','ср','чт','пт','сб','вс']


# In[11]:


# df = read_data()
# delta_morning,delta_evening = count_deltas(df)

# history_table = generate_history_table(df)
# input_table = generate_input_table(df)

# response = template.format(history_table=history_table,
#                 morning_delta = delta_morning,evening_delta=delta_evening,input_table = input_table)
# open('result.html','w').write(response)


# In[ ]:


z = None

import base64

key = open('password.txt','rb').read()
key = base64.b64encode(key).decode('utf-8')

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET_real(self):
        df = read_data()
        delta_morning,delta_evening = count_deltas(df)

        history_table = generate_history_table(df)
        input_table = generate_input_table(df)

        response = template.format(history_table=history_table,
                        morning_delta = delta_morning,evening_delta=delta_evening,input_table = input_table)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def do_POST_real(self):
        data_string = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
        data_string = urllib.parse.unquote(data_string)
        print(data_string)
        data_string = urllib.parse.unquote(data_string)
        params = data_string.split('&')

        conn = sqlite3.connect('mydb.sqlite')
        cur=conn.cursor() 
        for param in params:
            who,date,morning = param.split('|')
            morning = int(morning[0])
            sql = 'INSERT INTO Smenas (who,`when`,morning) VALUES (?,?,?)'
            cur.execute(sql, [who,date,morning])
        conn.commit()
        cur.close()
        conn.close()
        
        self.do_GET_real()

    def do_AUTHHEAD(self):
        #print "send header"
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        global key
        ''' Present frontpage with user authentication. '''
        if self.headers['Authorization'] == None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received')
            pass
        elif self.headers['Authorization'] == 'Basic '+key:
            self.do_GET_real()
            pass
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers['Authorization'])
            self.wfile.write('not authenticated')
            pass

    def do_POST(self):
        global key
        ''' Present frontpage with user authentication. '''
        if self.headers['Authorization'] == None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received')
            pass
        elif self.headers['Authorization'] == 'Basic '+key:
            self.do_POST_real()
            pass
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers['Authorization'])
            self.wfile.write('not authenticated')
            pass

httpd = HTTPServer(('0.0.0.0', 8080), SimpleHTTPRequestHandler)
httpd.serve_forever()


# In[ ]:


data_string = self.rfile.read(int(self.headers['Content-Length']))

