
import threading
import datetime, time
import socket
from pycomm3 import LogixDriver
import json
from tag_lists import *
from plc_utils import *
from keyence_utils import *
from export_data import *
from colorama import Fore, Style
from utils import *
##################### LOGGING ###########################
import logging
# import inspect
import datetime
import time as sleep_time  # Rename the time module import
#     
# handler.close()
# logger.removeHandler(handler)
#########################################################
spec_map = {}
event = threading.Event()
kill_threads = threading.Event()
part_program = 0
# logger.info("___Program Started___")
# def print_color(message:str)->None:
#     machine_num = str(extract_machine_num(message))
#     if machine_num == '3':
#         print_green(message)
#     elif machine_num == '4':
#         print_blue(message)
#     elif machine_num == '5':
#         print_yellow(message)


# def print_green(message:str)->None:
#     # message = Fore.GREEN + f"{message}\n" + Style.RESET_ALL
#     logger_r3.info(message)
#     print(Fore.GREEN + f"{message}\n" + Style.RESET_ALL)
# def print_blue(message:str)->None:
#     logger_r4.info(message)
#     print(Fore.BLUE + f"{message}" + Style.RESET_ALL)
# def print_yellow(message:str)->None:
#     logger_r5.info(message)
#     print(Fore.YELLOW + f"{message}" + Style.RESET_ALL)
# def print_red(message:str)->None:
#     logger_r3.critical(message)
#     logger_r4.critical(message)
#     logger_r5.critical(message)
#     print(Fore.RED + f"{message}" + Style.RESET_ALL)
def read_config()->dict:
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars
class create_cycle:
    def __init__(self, machine_num, keyence_ip):   
        self.self = self
        self.machine_num = machine_num
        self.keyence_ip = keyence_ip
        self.current_stage = 0
    def start(self):
        self.current_stage = 0
        self.thread = threading.Thread(target=self.cycle, args=[self.machine_num, self.keyence_ip], name=f"machine_{self.machine_num}")
        self.thread.start()
    def cycle(self, machine_num, keyence_ip):
        kill_threads.clear()
        event.wait()
        sleep_time.sleep(.05)
        config_info = read_config()
        print_color(f'({machine_num}) Sequence Started\n({machine_num}) Connecting to PLC at {config_info["plc_ip"]}\n({machine_num}) Connecting to Keyence at {keyence_ip}\n')
        scan_duration = 0 # keeping track of scan time in MS
        with LogixDriver(config_info['plc_ip']) as plc: #context manager for plc connection, currently resetting connection after ~24 hrs to avoid issues
            print_color(f'({machine_num}) PLC Connection Successful...\n({machine_num}) Keyence_{machine_num} Connection Successful...\n')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Keyence socket connections
            sock.connect((keyence_ip, 8500))
           # setKeyenceRunMode(machine_num, sock)
            write_plc_fault_flush(plc,machine_num) # Fault Codes and raise ready
            connection_timer = datetime.datetime.now() #reset connection timer
            while(True):
                if(kill_threads.is_set()): #check reset at beginning of cycle
                    print_red(f'({machine_num}) kill_threads detected at cycle start! Restarting threads...\n')
                    # break # Here we need to exit or kill the current thread and restart it
                    create_cycle(machine_num, keyence_ip).start() # restart the cycle by creating a new thread
                #spec_map = check_keyene_spec(sock, spec_map)
                part_type,reset_check,tag_data = get_status_info(machine_num, plc).values()#get part type and reset check from PLC
                if (reset_check[config_info['tags']['Reset']][1]):
                    reset_plc_tags(plc, machine_num,'type_one')
                    self.current_stage = 0
                    kill_threads.set()
                #################### STAGE ZERO ####################   
                if(self.current_stage == 0):
                    start_stage_zero(machine_num, plc, sock, self.current_stage) #stage 0 function
                    while(tag_data[config_info['tags']['LoadProgram']][1] != True): #Looping until LOAD PROGRAM goes high  # Data from PLC is only valid while LOAD_PROGRAM is low
                        if (kill_threads.is_set()): #check for reset at beginning of cycle
                            print_red(f'({machine_num})[STAGE:0] RESET detected while waiting for Load Program! Restarting thread...\n')
                            # break
                            create_cycle(machine_num, keyence_ip).start()

                        tag_data,reset_check = get_stage_zero_data(plc,machine_num).values() #get data from PLC
                        if (reset_check[config_info['tags']['Reset']][1] == True):
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num,'type_one')
                            kill_threads.set()
                        sleep_time.sleep(.050) # 5ms pause between reads
                    if (kill_threads.is_set()): #check for reset at beginning of cycle
                        # break
                        create_cycle(machine_num, keyence_ip).start()
                    print_color(f'({machine_num}) PLC(LOAD_PROGRAM) activated. Retrieving part data and program number...') # Once PLC(LOAD_PROGRAM) goes high, mirror data and set Phoenix(READY) high, signifies end of "loading" process
                    swap_check, part_program, part_type = stage_zero_preLoad(machine_num, plc, sock).values()
                    if swap_check == 0: # reset threads if invalid part type
                        kill_threads.set()
                    part_type = tag_data[config_info['tags']['PartType']][1]
                    print_color(f'({machine_num})[STAGE:0] PRE-LOAD: Part Type({part_type})')
                    keyence_string = keyence_string_generator(machine_num, part_type, tag_data, sock, config_info) #building out external Keyence string for scan file naming
                    if keyence_string == 'ERROR':
                        kill_threads.set()                               
                    stage_zero_load(plc, sock, machine_num, tag_data,keyence_string) 
                    self.current_stage += 1 #increment current stage to proceed forward
                #################### STAGE ONE ####################
                elif self.current_stage == 1:
                    print_yellow(f'({machine_num})[STAGE:1] Waiting for START_PROGRAM...\n')
                    while not tag_data[config_info['tags']['StartProgram']][1]: #looping until PLC(START_PROGRAM) goes high
                        if (kill_threads.is_set()): #check for reset at beginning of cycle
                            print_red(f'({machine_num})[STAGE:1] RESET detected while waiting for START_PROGRAM\n')
                            # break
                            create_cycle(machine_num, keyence_ip).start()
                        tag_data = read_plc_dict(plc, machine_num) #continuous PLC read
                        if tag_data[config_info['tags']['Reset']][1]: #check for reset during cycle
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num, 'type_two') # type_two reset for stage 1
                            kill_threads.set()
                        sleep_time.sleep(0.050)
                    print_color(f'({machine_num})[STAGE:1] PLC(START_PROGRAM) activated!\n')
                    exe_time,tag_data,start_trigger_timer = stage_one_trigger(plc, sock, machine_num, tag_data).values()
                    if (exe_time > 3000): # measure time it took to trigger keyence, if greater than 3 seconds, set fault
                        write_plc_fault(plc, machine_num, 2)
                    scan_duration,exe_time,tag_data= stage_one_post_trigger(plc, sock, machine_num, tag_data, start_trigger_timer).values()
                    if exe_time > 3000:
                        write_plc_fault(plc, machine_num, 3)

                    end_stage_one(plc, machine_num, sock, tag_data, scan_duration, keyence_string, part_type, part_program)
                    print_color(f'({machine_num})[STAGE:1] Complete!\n')
                    self.current_stage += 1
                #################### END STAGE ONE ####################
                elif self.current_stage == 2:  # Final Stage, reset to Stage 0 once PLC(END_PROGRAM) and PHOENIX(DONE) have been set low
                    write_plc_single(plc, machine_num, 'Done', True)
                    print_color(f'({machine_num})[STAGE:2] Waiting for PLC(ENDPROGRAM)\n')
                    while not tag_data[config_info['tags']['EndProgram']][1]:
                        if kill_threads.is_set():
                            print_red(f'({machine_num}) kill_threads detected while waiting for ENDPROGRAM! Restarting threads...\n')
                            # break
                            create_cycle(machine_num, keyence_ip).start()
                        tag_data = read_plc_dict(plc, machine_num)  # continuous PLC read
                        if tag_data[config_info['tags']['Reset']][1]:
                            print_color(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...\n')
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num, 'type_two')  # type_two reset for stage 2
                            kill_threads.set()
                        sleep_time.sleep(0.050)  # 5ms pause between reads
                    reset_toEnd_cycle(plc, machine_num, sock)  # reset PLC tags to end cycle
                    self.current_stage = 0  # cycle complete, reset to stage 0
                if abs(datetime.datetime.now() - connection_timer).total_seconds() > 86400:
                    print_red(f'({machine_num}) Connection reset detected! restarting threads...\n')
                    connection_timer = datetime.datetime.now()
                    kill_threads.set()
                if (kill_threads.is_set()): #check for reset at beginning of cycle
                    print_red(f'({machine_num}) kill_threads detected at cycle end! Restarting threads...\n')
                    # self.current_stage = 0
                    # break  # Kill thread if global is set True for any reason
                    create_cycle(machine_num, keyence_ip).start()
                sleep_time.sleep(0.005)  # artificial loop timer
  
#END class Cycler
def heartbeat(machine_num): #sets PLC(Heartbeat) high every second to verify we're still running and communicating
    config_info = read_config()
    def write_heartbeat(plc, machine_num):
        try:
            write_plc_single(plc, machine_num, 'HeartBeat', True)
        except Exception as error:
            print_red(f'({machine_num}-HB) Exception in Heartbeat {error}')
            kill_threads.set()
    with LogixDriver(config_info['plc_ip']) as plc:
        print_color(f'({machine_num}-HB) Heartbeat thread connected to PLC.\n')
        # while (True):
        counter = 0
        while not (kill_threads.is_set()):
            write_heartbeat(plc, machine_num)
            if (counter % 200) == 0:
                print(f"({machine_num}-HB) Active PLC Connection",end='\r')
            counter += 1
            sleep_time.sleep(1)
        print_red(f'({machine_num}-HB) Heartbeat: kill_threads high or reset event set, restarting all threads')
        if (kill_threads.is_set()):
            # kill_threads.clear()
            heartbeat(machine_num)
   
# END heartbeat
def main():
    config_info = read_config()  # Read configuration information
    cycle_threads = []  # Store created cycle threads
    heartbeat_threads = []  # Store created heartbeat threads
# initilize each loop seperatly and then start them all at once each in thier own loop

    for machine_num in list(config_info['mnKeyenceIP'].keys()):  # Loop through machines in config
        ip = config_info['mnKeyenceIP'][machine_num]
        cycle_object = create_cycle(machine_num, ip)
        cycle_object.start()  # Start the cycle thread
        cycle_threads.append(cycle_object)

        heartbeat_thread = threading.Thread(target=heartbeat, args=[machine_num], name=f"{machine_num}_heartBeat")
        heartbeat_thread.start()
        heartbeat_threads.append(heartbeat_thread)

    event.set()  # Signal threads to start

    while not kill_threads.is_set():
        for cycle_obj in cycle_threads:
            if cycle_obj.thread is not None and not cycle_obj.thread.is_alive():
                # Thread has completed or was killed, restart it
                cycle_obj.start()

        # You can add a delay here if you don't want to check the threads continuously
        sleep_time.sleep(5)

    # Properly clean up resources when the main thread exits
    for cycle_thread, heartbeat_thread in zip(cycle_threads, heartbeat_threads):
        if cycle_thread.thread is not None:
            cycle_thread.thread.join()
        heartbeat_thread.join()




# def main():
#     config_info = read_config()
#     cycle_list = []
#     thread_list = []
#     for i in list(config_info['mnKeyenceIP'].keys()):
#         ip = config_info['mnKeyenceIP'][i]
#         cycle_object = create_cycle(i, config_info['mnKeyenceIP'][i])
#         # filePath = os.path.join(config_info['FTP_directory'] + ip + config_info['FTP_extension'])
#         cycle_list.append(cycle_object)
#         cycle_thread = threading.Thread(target=cycle_object.cycle, args=[str(i), ip], name= 'machine_'+ str(i))
#         heartbeat_threads = threading.Thread(target=heartbeat, args=[str(i)], name=f"{str(i)}_heartBeat")
#         thread_list.append(cycle_thread)
#         thread_list.append(heartbeat_threads)
#         cycle_thread.start()
#         heartbeat_threads.start()    
#     event.set()
#     for i in thread_list:
#         i.join()
# #END 'main'

if __name__ == '__main__':
    while True:
        main()

