#from platform import machine
import threading
import datetime, time
import socket
#import csv
#from logging import debug
from pycomm3 import LogixDriver
#from pycomm3.cip.data_types import DINT, UINT, SINT
import json
#import os
from tagLists import *
from plcFuncs import *
from keyenceFuncs import *
from fileCreate import *

##################### LOGGING ###########################
import time
import logging

from inspect import currentframe, getframeinfo
#########################################################
'''
DEBUG
INFO
WARNING
ERROR
CRITICAL
The default level is WARNING, 
only events of this level and above will be tracked, 
unless the logging package is configured to do otherwise.
-> level=logging.WARNING
'''
frame = getframeinfo(currentframe())
path = frame.filename
filename = path.split("/")[-1]
fn = filename.rsplit(".")[0]
today = datetime.date.today().strftime("%a-%b-%d-%Y")
now = datetime.datetime.now().strftime("%I:%M:%S.%f")[:-3]
logging.basicConfig(level=logging.WARNING, filename = f"{today}.log",filemode = "w",
format = f"{now}-%(levelname)s-%(message)s")
logger = logging.getLogger(fn)
#Create File handler
handler = logging.FileHandler(f"{fn}-{today}.log")  
#Create logging format
formatter = logging.Formatter(f"{now}-{fn}-%(levelname)s-%(message)s")
#Add format to handler
handler.setFormatter(formatter)
#add the file handler to the logger
logger.addHandler(handler)
### END LOGGING ###



### GLOBALS ########################################################

specDict = {}
event = threading.Event()
kill_threads = threading.Event()

# END GLOBALS ####################################################

#reads config file into dict
def read_config():
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars
#END
 

# primary function, to be used by 14/15 threads
class cycler:
    def __init__(self, machine_num, keyence_ip):
    
        self.self = self
        self.machine_num = machine_num
        self.keyence_ip = keyence_ip
        self.current_stage = 0

    def cycle(self, machine_num, keyence_ip):
        kill_threads.clear()
        event.wait()
        time.sleep(.05)
        print(f'CYCLE for Machine {machine_num} Started')

        config_info = read_config()


        scan_duration = 0 # keeping track of scan time in MS

        print(f'({machine_num}) Connecting to PLC...\n')
        logger.info(f'({machine_num}) Connecting to PLC...\n')
        with LogixDriver(config_info['plc_ip']) as plc: #context manager for plc connection, currently resetting connection after ~24 hrs to avoid issues
            print(f'({machine_num}) Connected to PLC')

            #try:

                
            # Keyence socket connections
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((keyence_ip, 8500))
            print(f'({machine_num}) Connected to Keyence at {keyence_ip}\n')
           # print("Setting Keyence to Run Mode...")
           # setKeyenceRunMode(machine_num, sock)
           # print("Keyence run mode set...")
            logger.info(f'({machine_num}) Connected to Keyence at {keyence_ip}\n')
            # clearing potential fault info when resetting
            write_plc_single(plc, machine_num, 'Faulted', False)
            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
            write_plc_single(plc, machine_num, 'FaultStatus', 0)
            write_plc_single(plc, machine_num, 'Done', False)
            write_plc_single(plc, machine_num, 'Pass', False)
            write_plc_single(plc, machine_num, 'Busy', False)
            write_plc_single(plc, machine_num, 'Fail', False)

            write_plc_single(plc, machine_num, 'Ready', True)
        
            connection_timer = datetime.datetime.now() #reset connection timer
            

            ###########################
            #      CYCLE START        #
            ###########################

            while(True):

                if(kill_threads.is_set()): #check reset at beginning of cycle
                    print(f'({machine_num}) kill_threads detected at cycle start! Restarting threads...')
                    # logger.warning(f'({machine_num}) kill_threads detected at cycle start! Restarting threads...')
                    break
                #specDict = checkKeyeneSpec(sock, specDict)
                print(f'({machine_num}) Reading PLC\n')
                # logger.info(f'({machine_num}) Reading PLC\n')
                results_dict = read_plc_dict(plc, machine_num) #initial PLC tag read
                PartT = results_dict[config_info['tags']['PartType']][1]
                # print(f'({machine_num}) {results_dict}')
                
                # PLC read and check to reset system off PLC(Reset) tag
                reset_check = read_plc_single(plc, machine_num, 'Reset')
                if (reset_check[config_info['tags']['Reset']][1] == True):
                    print(f'({machine_num}) (Pre-Load) Reset Detected! Setting back to Stage 0...')
                    # logger.warning(f'({machine_num}) (Pre-Load) Reset Detected! Setting back to Stage 0...')
                    self.current_stage = 0

                    print(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                    # logger.info(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                    write_plc_flush(plc,machine_num)
                    write_plc_single(plc, machine_num, 'Faulted', False)
                    write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                    write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                    write_plc_single(plc, machine_num, 'FaultStatus', 0)
                    kill_threads.set()

                ######################
                #      STAGE 0       #
                ######################            
                if(self.current_stage == 0):
                    print(f'({machine_num}) We are in stage0...\n')
                    checkKeyenceError(machine_num, sock, plc) #check keyence for error codes

                    print(f'({machine_num}) Setting Boolean Flags for Stage 0\n') #flag reset/beginning of timing diagram
                    # logger.info(f'({machine_num}) Setting Boolean Flags for Stage 0\n')
                    write_plc_single(plc, machine_num, 'Done', False)
                    write_plc_single(plc, machine_num, 'Pass', False)
                    write_plc_single(plc, machine_num, 'Busy', False)
                    write_plc_single(plc, machine_num, 'Fail', False)

                    write_plc_single(plc, machine_num, 'Ready', True)
                    
                    ########################################################
                    # When LOAD PROGRAM goes HIGH and BUSY goes low        #
                    # Send all data to PLC (ex.Program #,Branch #, Scan #) #
                    ########################################################
                    print(f'({machine_num}) Stage 0 : Listening for PLC(LOAD_PROGRAM) to go HIGH\n({machine_num}) Waiting for PLC(BUSY) to go LOW') #reading PLC until LOAD_PROGRAM goes high
                    # logger.info(f'({machine_num}) Stage 0 : Listening for PLC(LOAD_PROGRAM) = 1\n')
                    while(results_dict[config_info['tags']['LoadProgram']][1] != True): #Looping until LOAD PROGRAM goes high 
                        
                       
                        if (kill_threads.is_set()):
                            print(f'({machine_num}) kill_threads detected while waiting for LOAD! Restarting threads...')
                            # logger.warning(f'({machine_num}) kill_threads detected while waiting for LOAD! Restarting threads...')
                            break
                        results_dict = read_plc_dict(plc, machine_num) #continuous full PLC read
                        
                        reset_check = read_plc_single(plc, machine_num, 'Reset') #single plc tag read
                        if (reset_check[config_info['tags']['Reset']][1] == True):
                            print(f'({machine_num}) (Pre-Load) Reset Detected! Setting back to Stage 0...')
                            # logger.warning(f'({machine_num}) (Pre-Load) Reset Detected! Setting back to Stage 0...')
                            self.current_stage = 0
                            print(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            # logger.info(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            write_plc_flush(plc,machine_num)
                            write_plc_single(plc, machine_num, 'Faulted', False)
                            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                            write_plc_single(plc, machine_num, 'FaultStatus', 0)
                            kill_threads.set()
                        time.sleep(.050) # 5ms pause between reads
                    if kill_threads.is_set():
                        break
                    print(f'({machine_num}) PLC(LOAD_PROGRAM) went HIGH! preparing to drop READY')
                    print(f'({machine_num}) Gathering part data and program number...')
                    # logger.info('PLC(LOAD_PROGRAM) went high!\n')


                    results_dict = read_plc_dict(plc, machine_num)
                    results_dict_og = results_dict.copy()
                    PartT = results_dict[config_info['tags']['PartType']][1]
                    swapCheck = KeyenceSwapCheck(sock, machine_num, PartT) #ensure keyence has proper program loaded   
                    if swapCheck == 0:
                        kill_threads.set()
                    
                    
                    # Once PLC(LOAD_PROGRAM) goes high, mirror data and set Phoenix(READY) high, signifies end of "loading" process
                    write_plc_single(plc, machine_num, 'Ready', False)
                    print(f'({machine_num}) Dropping Phoenix(READY) low.\n')
                    # logger.info(f'({machine_num}) Dropping Phoenix(READY) low.\n')

                    #################### Mirror ############################
                    print(f'({machine_num}) !Mirroring Data!\n')
                    # logger.info(f'({machine_num}) !Mirroring Data!\n')
                    write_plc(plc,machine_num,results_dict_og)
                    ############################################################

                    PartT = results_dict[config_info['tags']['PartType']][1]
                    print(f'({machine_num}) READING PARTTYPE AFTER LOAD AS : ',PartT)
                    # logger.info(f'({machine_num}) READING PARTTYPE AFTER LOAD AS : ',PartT)
                    keyence_string = keyence_string_generator(machine_num, PartT, results_dict, sock, config_info) #building out external Keyence string for scan file naming
                    if keyence_string == 'ERROR':
                        kill_threads.set()
                
                    


                    pun_str = int_array_to_str(results_dict['PUN'][1])

                    datetime_info_len_check = [str(results_dict[config_info['tags']['Month']][1]), str(results_dict[config_info['tags']['Day']][1]), str(results_dict[config_info['tags']['Hour']][1]), str(results_dict[config_info['tags']['Minute']][1]), str(results_dict[config_info['tags']['Second']][1])]

                    #confirming all date/time fields are 2 digits (except year)
                    
                    for x in range(0,len(datetime_info_len_check)):
                        if(int(datetime_info_len_check[x]) < 10):
                            datetime_info_len_check[x] = '0' + datetime_info_len_check[x]

                    keyence_string = str(pun_str[10:22]) + '_' + str(results_dict[config_info['tags']['Year']][1]) + '-' + datetime_info_len_check[0] + '-' + datetime_info_len_check[1] + '-' + datetime_info_len_check[2] + '-' + datetime_info_len_check[3] + '-' + datetime_info_len_check[4] + '_' + keyence_string
                    
                    print(f'({machine_num}) LOADING : {keyence_string}')
                    logger.info(f'({machine_num}) LOADING : {keyence_string}')
                    loadKeyence(sock, machine_num, str(results_dict[config_info['tags']['PartProgram']][1]), keyence_string ) #Keyence loading message, uses PartProgram from PLC to load specific branch
                    print(f'({machine_num}) Keyence Loaded!\n')
                    logger.info(f'({machine_num}) Keyence Loaded!\n')

            
                    write_plc_single(plc, machine_num, 'Ready', True)
                    self.current_stage += 1 #incrementing out of STAGE0
                #END STAGE0


                #START STAGE1 : START/END Program
                elif(self.current_stage == 1):
                    print(f'({machine_num}) Stage 1! Listening for STARTPROGRAM\n')
                    logger.info(f'({machine_num}) Stage 1! Listening for STARTPROGRAM\n')
                    while(results_dict[config_info['tags']['StartProgram']][1] != True):
                        if (kill_threads.is_set()):
                            print(f'({machine_num}) kill_threads detected while waiting for START! Restarting threads...')
                            logger.warning(f'({machine_num}) kill_threads detected while waiting for START! Restarting threads...')
                            break
                        results_dict = read_plc_dict(plc, machine_num) # continuous PLC read
                        

                        if (results_dict[config_info['tags']['Reset']][1] == True):
                            print(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...')
                            logger.warning(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...')
                            self.current_stage = 0
                            print(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            logger.info(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            write_plc_flush(plc,machine_num)

                            write_plc_single(plc, machine_num, 'Reset', False)
                            write_plc_single(plc, machine_num, 'Faulted', False)
                            write_plc_single(plc, machine_num, 'FaultStatus', 0)
                            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                            kill_threads.set()
                    
                        time.sleep(.050) # 5ms pause between reads

                
                    #Update part type and part program if needed
                    results_dict = read_plc_dict(plc, machine_num)
                    print(f'({machine_num}) StartProgram went high!\n')
                    logger.info(f'({machine_num}) StartProgram went high!\n')

                    start_timer_Trigger_to_Busy = datetime.datetime.now()
                    #Actual Keyence Trigger (T1) here***
                    TriggerKeyence(sock, machine_num)
                    print(f'({machine_num}) Keyence Triggered!\n')
                    logger.info(f'({machine_num}) Keyence Triggered!\n')
                    start_timer_T1_to_EndProgram = datetime.datetime.now()
                    time_diff = (start_timer_T1_to_EndProgram - start_timer_Trigger_to_Busy)
                    execution_time = time_diff.total_seconds() * 1000
                    if(execution_time > 3000):
                        print(f'({machine_num}) TriggerKeyence timeout fault (longer than 3 seconds)! PhoenixFltCode : 2')
                        logger.error(f'({machine_num}) TriggerKeyence timeout fault (longer than 3 seconds)! PhoenixFltCode : 2')
                        
                        write_plc_single(plc, machine_num, 'PhoenixFltCode', 2)
                        write_plc_single(plc, machine_num, 'FaultStatus', 2)
                        write_plc_single(plc, machine_num, 'Faulted', True)
                        

                    write_plc_single(plc, machine_num, 'Ready', False)

                    #BUSY BEFORE KEYENCE TRIGGER TEST ***
                    write_plc_single(plc, machine_num, 'Busy', True)
                    
                    monitor_endScan(plc, machine_num, sock) # ends Keyence with EndScan
                    end_timer_T1_to_EndScan = datetime.datetime.now()
                    diff_timer_T1_to_EndScan = (end_timer_T1_to_EndScan - start_timer_T1_to_EndProgram)
                    execution_time = diff_timer_T1_to_EndScan.total_seconds() * 1000
                    scan_duration = execution_time #for logging in .csv

                    
                    write_plc_single(plc, machine_num, 'Busy', False)


                    keyence_result_check_start = datetime.datetime.now()
                    monitor_KeyenceNotRunning(sock, machine_num) # verify Keyence has processed results and written out FTP files
                    keyence_result_check_end = datetime.datetime.now()
                    time_diff = (keyence_result_check_end - keyence_result_check_start)
                    execution_time = time_diff.total_seconds() * 1000
                    if(execution_time > 3000):
                        print(f'({machine_num}) KeyenceNotRunning timeout (took longer than 3 seconds)! PhoenixFltCode : 3')
                        logger.error(f'({machine_num}) KeyenceNotRunning timeout (took longer than 3 seconds)! PhoenixFltCode : 3')
                        write_plc_single(plc, machine_num, 'PhoenixFltCode', 3)
                        write_plc_single(plc, machine_num, 'FaultStatus', 3)
                        write_plc_single(plc, machine_num, 'Faulted', True)

                    

                    keyence_results = []
                    keyence_results = keyenceResults_to_PLC(sock, plc, machine_num)

                    create_csv(machine_num, results_dict, keyence_results, keyence_string, scan_duration) # results to .csv, PER SCAN

                    #check if we're ready to write out a parts results, PER PART
                    #write_part_results(machine_num, results_dict, keyence_results, keyence_string) #appends to result string, writes out file and clears string if on final scan of part

                    # Setting Chinmay's Keyence tag high
                    keyence_msg = 'MW,#PhoenixControlContinue,1\r\n'
                    sock.sendall(keyence_msg.encode())
                    print(f'({machine_num}) Sent \'#PhoenixControlContinue,1\' to Keyence!')
                    logger.info(f'({machine_num}) Sent \'#PhoenixControlContinue,1\' to Keyence!')
                    data = sock.recv(32) #obligatory Keyence read to keep buffer clear

                    print(f'({machine_num})Stage 1 Complete!\n')
                    self.current_stage += 1

                #Final Stage, reset to Stage 0 once PLC(END_PROGRAM) and PHOENIX(DONE) have been set low
                elif(self.current_stage == 2):
                    write_plc_single(plc, machine_num, 'Done', True)
                    print(f'({machine_num}) Stage 2 : Listening for PLC(ENDPROGRAM) high to reset back to Stage 0\n')
                    logger.info(f'({machine_num}) Stage 2 : Listening for PLC(ENDPROGRAM) high to reset back to Stage 0\n')
                    
                    while(results_dict[config_info['tags']['EndProgram']][1] != True):
                        if (kill_threads.is_set()):
                            print(f'({machine_num}) kill_threads detected while waiting for ENDPROGRAM! Restarting threads...')
                            logger.warning(f'({machine_num}) kill_threads detected while waiting for ENDPROGRAM! Restarting threads...')
                            break
                        results_dict = read_plc_dict(plc, machine_num) # continuous PLC read
                        

                        if (results_dict[config_info['tags']['Reset']][1] == True):
                            print(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...')
                            logger.warning(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...')
                            self.current_stage = 0
                            print(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                            write_plc_flush(plc,machine_num)
                            write_plc_single(plc, machine_num, 'Reset', False)
                            write_plc_single(plc, machine_num, 'Faulted', False)
                            write_plc_single(plc, machine_num, 'FaultStatus', 0)
                            write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
                            write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
                            kill_threads.set()
                            
                    
                        time.sleep(.050) # 5ms pause between reads

                

                    print(f'({machine_num}) PLC(END_PROGRAM) is high. Dropping PHOENIX(DONE) low\n')
                    logger.info(f'({machine_num}) PLC(END_PROGRAM) is high. Dropping PHOENIX(DONE) low\n')
                    write_plc_single(plc, machine_num, 'Done', False)
                    write_plc_single(plc, machine_num, 'Pass', False)
                    write_plc_single(plc, machine_num, 'Busy', False)
                    write_plc_single(plc, machine_num, 'Fail', False)

                    write_plc_single(plc, machine_num, 'Aborted', False)
                    

                    print(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                    logger.info(f'({machine_num}) Flushing PLC(Result) tag data...\n')
                    write_plc_flush(plc,machine_num) # defaults all .I Phoenix tags at start of cycle
                    write_plc_single(plc, machine_num, 'Ready', True)
                    self.current_stage = 0 # cycle complete, reset to stage 0
                    

                if (abs(datetime.datetime.now() - connection_timer).total_seconds() > 86400):
                    print(f'({machine_num}) Connection reset detected! restarting threads...')
                    logger.warning(f'({machine_num}) Connection reset detected! restarting threads...')
                    connection_timer = datetime.datetime.now()
                    kill_threads.set()

                if (kill_threads.is_set()):
                    print(f'({machine_num}) kill_threads detected at cycle end! Restarting threads...')
                    logger.warning(f'({machine_num}) kill_threads detected at cycle end! Restarting threads...')
                    break # Kill thread if global is set True for any reason
                time.sleep(.005) #artificial loop timer


            #if something goes wrong while 'cycle' is looping
            '''except ConnectionRefusedError:
                print(f'({machine_num}) Connection Refused!')
            except ConnectionResetError:
                print(f'({machine_num}) Connection Reset!')
            except TimeoutError:
                print(f'({machine_num}) Connection Timed Out!')
            except KeyError as key_error:
                print(f'({machine_num}) KeyError: {key_error}') 
            except Exception as e:
                if str(e) == '[WinError 10054] An existing connection was forcibly closed by the remote host':
                    print(f'({machine_num}) Keyence Connection Error, sending PhoenixFltCode: 1')
                    kill_threads.set()
                elif str(e) == 'failed to receive reply':
                    print(f'({machine_num}) Keyence Connection Error, sending PhoenixFltCode: 4')
                    kill_threads.set()
                else:
                    print(f'({machine_num}) Exception: {e}')'''
#END class Cycler
            

#sets PLC(Heartbeat) high every second to verify we're still running and communicating
def heartbeat(machine_num):
    config_info = read_config()
    with LogixDriver(config_info['plc_ip']) as plc:
        print(f'({machine_num}) Heartbeat thread connected to PLC. Writing \'Heartbeat\' high every 1 second\n')
        logger.debug(f'({machine_num}) Heartbeat thread connected to PLC. Writing \'Heartbeat\' high every 1 second\n')
        counter = 0
        while(True):
            try:
                write_plc_single(plc, machine_num, 'HeartBeat', True) 
            except Exception as e:
                print(f'({machine_num}) Exception in Heartbeat {e}')
                kill_threads.set()
            #print(read_plc_single(plc, machine_num, 'HeartBeat'))
            #plc.write('Program:HM1450_VS' + machine_num + '.VPC1.I.Heartbeat', True)
            #print(f'({machine_num}) Heartbeat written HIGH')
            if (counter%200) == 0:
                print(f'({machine_num}) Active Connecion\t')
            counter += 1
            time.sleep(1)
            if (kill_threads.is_set()):
                print(f'({machine_num}) Heartbeat : kill_threads high, restarting all threads')
                logger.warning(f'({machine_num}) Heartbeat : kill_threads high, restarting all threads')
                break # Kill thread if global is set True for any reason
#END heartbeat




#START main()
def main():

    config_info = read_config()

    cyclers = []
    threads = []
    for i in list(config_info['mnKeyenceIP'].keys()):
        ip = config_info['mnKeyenceIP'][i]
        cyclerObj = cycler(i, config_info['mnKeyenceIP'][i])
        filePath = os.path.join(config_info['FTP_directory'] + ip + config_info['FTP_extension'])
        cyclers.append(cyclerObj)

        cycleT = threading.Thread(target=cyclerObj.cycle, args=[str(i), ip], name= 'machine_'+ str(i))
        heartbeatT = threading.Thread(target=heartbeat, args=[str(i)], name=str(i) + '_heartBeat')
        threads.append(cycleT)
        threads.append(heartbeatT)
    
        cycleT.start()
        heartbeatT.start()

    
    event.set()
    for i in threads:
        i.join()

    

#END 'main'

#implicit 'main()' declaration
if __name__ == '__main__':
    while(True):
        main()
