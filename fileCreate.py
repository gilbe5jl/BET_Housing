from plcFuncs import int_array_to_str
import datetime
import os
import sys
import json
from tagLists import *

with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
    config_data = config_file.read()
    config_info = json.loads(config_data)

input_tags = input_tag_list(2)
results_tags = result_tag_list()


def create_csv(machine_num:str, results:dict, keyence_results:list, face_name:str, duration:int,part_type,part_program):
    '''
    Results data is written to a CSV file 
    The CSV file is used by the HMI 
    '''
    file_name = config_info['FTP_directory'] + config_info['mnKeyenceIP'][machine_num] + config_info['FTP_extension']
    file_name = file_name + '\\' + face_name + '.txt'
    if not os.path.exists(os.path.dirname(file_name)):
       os.makedirs(os.path.dirname(file_name))
    file_name = file_name.replace('\x00', '')
    print(f'Creating CSV files:\t->{file_name}')
    with open(file_name, 'w+', newline='') as f:
       for i in input_tags:
           try:
                if i == 'PUN':
                    # print(f"\n\t\tPUN:{results['PUN'][1]}\n\n")
                    result = int_array_to_str(results[i][1])            
                    f.write(f"{i}_2, {result}\n")
                    print(i, str(results[i][1]))
                elif i == 'PASS':
                    # result = str(0)
                    # f.write(f"{i}_2, {result}\n")
                    print(f"PASS->{i}", str(results[i][1]))
                else:
                    if i == 'PART_PROGRAM':
                        f.write(f"PART_PROGRAM_2, {part_program}\n")
                    elif i == 'PART_TYPE':
                        f.write(f"PART_TYPE_2, {part_type}\n")
                    else:
                        result = str(results[i][1])
                        f.write(f"{i}_2, {result}\n")
                        print(i, str(results[i][1]))
           except KeyError as error:
               print(error)
       for i in range(len(results_tags)):
           try:
               f.write(f"{results_tags[i]}_2, {str(keyence_results[i])}  \n")
           except KeyError as error:
               print("A Key ERROR occured while creating CSV file",error)
       f.write('DURATION_2, ' + str(duration) + '\n')
#END create_csv
 
# Gerry's request to log all results per part in one continuous file
def write_part_results(machine_num:str, results_dict:dict, keyence_results:list, keyence_string:str):
    emptyStr = ''
    punStr = str(results_dict['PUN'][1])
    punStr = punStr.strip() # remove spaces                                                                       
    punStr = punStr.rstrip('\\x00') # remove nulls
    punStr = 'PUN: ' + punStr
    t = datetime.datetime.now()
    s = t.strftime('%Y-%m-%d %H:%M:%S.%f') # stripping off decimal (ms)
    dt_string = t.strftime("%Y-%m-%d") #datetime stamped file naming, year#-month#-day#
    # designating end of part by part #, to write out actual line in .csv
    writeStr = emptyStr.join(['Pass: ', str(keyence_results[3]), ', Fail: ', str(keyence_results[4])]) # final append to string before writing out to .txt file

    file_name = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop', 'results.txt') 

    #file_name = 'C:\\Users\\RyanC\Desktop\\parts_results_consolidated\\' + dt_string + '-machine_' + str(machine_num) + '.txt'
    with open(file_name, 'a+', newline='') as f:
        f.write(s[:-4] + ', ')
        f.write(keyence_string + ' ')
        #f.write(punStr + ', ')
        f.write(writeStr + '\n\n')
        print(f'({machine_num}) (WROTE) part_result : {writeStr}')
#END write_part_results