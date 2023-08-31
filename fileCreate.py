from plcFuncs import int_array_to_str
import datetime
import os
import sys
import json
from tagLists import *

with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
    config_data = config_file.read()
    config_info = json.loads(config_data)

Itags = ITagList(2)
Resultstags = resultTagList()


# George's request for a .csv file per inspection
def create_csv(machine_num:str, results:dict, keyence_results:list, face_name:str, duration:int):
    
    file_name = config_info['FTP_directory'] + config_info['mnKeyenceIP'][machine_num] + config_info['FTP_extension']
    file_name = file_name + '\\' + face_name + '.txt'
    if not os.path.exists(os.path.dirname(file_name)):
       os.makedirs(os.path.dirname(file_name))
    file_name = file_name.replace('\x00', '')
    print('Creating CSV called:',file_name)
    with open(file_name, 'w+', newline='') as f:
       for i in Itags:
           try:
               f.write(i + str(results[i][1]) + '\n')
           except KeyError as e:
               pass
       for i in range(len(Resultstags)):
           try:
               f.write(Resultstags[i] +str(keyence_results[i]) + '\n')
           except KeyError as e:
               pass
       f.write('DURATION' + str(duration) + '\n')
       return
#END create_csv
 
# Gerry's request to log all results per part in one continuous file


def write_part_results(machine_num:str, results_dict:dict, keyenceResults:list, keyence_string:str):
    emptyStr = ''
    punStr = str(results_dict['PUN'][1])
    punStr = punStr.strip() # remove spaces                                                                       
    punStr = punStr.rstrip('\\x00') # remove nulls
    punStr = 'PUN: ' + punStr
    t = datetime.datetime.now()
    s = t.strftime('%Y-%m-%d %H:%M:%S.%f') # stripping off decimal (ms)
    dt_string = t.strftime("%Y-%m-%d") #datetime stamped file naming, year#-month#-day#
    # designating end of part by part #, to write out actual line in .csv
    writeStr = emptyStr.join(['Pass: ', str(keyenceResults[3]), ', Fail: ', str(keyenceResults[4])]) # final append to string before writing out to .txt file

    file_name = 'E:\\part_results_consolidated\\' + dt_string + '-machine_' + str(machine_num) + '.txt'

    #file_name = 'C:\\Users\\RyanC\Desktop\\parts_results_consolidated\\' + dt_string + '-machine_' + str(machine_num) + '.txt'
    with open(file_name, 'a+', newline='') as f:
        f.write(s[:-4] + ', ')
        f.write(keyence_string)
        #f.write(punStr + ', ')
        f.write(writeStr + '\n\n')
        print(f'({machine_num}) (WROTE) part_result : {writeStr}')
#END write_part_results