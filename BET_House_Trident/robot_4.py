#####################
#     ROBOT 4       #
#####################
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
import datetime
import time as sleep_time  # Rename the time module import
spec_map = {}
event = threading.Event()
kill_threads = threading.Event()
part_program = 0

def read_config()->dict:
    with open(os.path.join(sys.path[0], 'config_r4.json'), "r") as config_file:
        config_data = config_file.read()
        config_map = json.loads(config_data)
        return config_map
class create_cycle:
    def __init__(self, machine_num, keyence_ip):   
        self.self = self
        self.machine_num = machine_num
        self.keyence_ip = keyence_ip
        self.current_stage = 0
    def cycle(self ):
        machine_num = self.machine_num
        keyence_ip = self.keyence_ip
        kill_threads.clear()
        event.wait()
        sleep_time.sleep(.05)
        config_info = read_config()
        print_color(f'\n({machine_num}) Sequence Started\n({machine_num}) Connecting to PLC at {config_info["plc_ip"]}\n({machine_num}) Connecting to Keyence at {keyence_ip}\n')
        scan_duration = 0 # keeping track of scan time in MS
        with LogixDriver(config_info['plc_ip']) as plc: #context manager for plc connection, currently resetting connection after ~24 hrs to avoid issues
            print_color(f'({machine_num}) PLC Connection Successful...\n({machine_num}) Keyence_{machine_num} Connection Successful...\n')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Keyence socket connections
            sock.connect((keyence_ip, 8500))
           # setKeyenceRunMode(machine_num, sock)
            write_plc_fault_flush(plc,machine_num) # Fault Codes and raise ready
            connection_timer = datetime.datetime.now() #reset connection timer
            while(True):
                if(kill_threads.is_set() ): #check reset at beginning of cycle
                    print_red(f'({machine_num}) kill_threads detected at cycle start! Restarting threads...\n')
                    break
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
                            print_red(f'({machine_num})[STAGE:0] RESET detected while waiting for Load Program. Restarting thread...\n')
                            break
                        tag_data,reset_check = get_stage_zero_data(plc,machine_num).values() #get data from PLC
                        if (reset_check[config_info['tags']['Reset']][1] == True):
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num,'type_one')
                            kill_threads.set()
                        sleep_time.sleep(.050) # 5ms pause between reads
                    if (kill_threads.is_set()): #check for reset at beginning of cycle
                        break
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
                            break
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
                            break
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
                    self.current_stage = 0
                    break  
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
        print_color(f'({machine_num}-HB) Heartbeat connected to PLC.\n')
        # while (True):
        counter = 0
        while not (kill_threads.is_set()):
            write_heartbeat(plc, machine_num)
            if (counter % 200) == 0:
                print(f"({machine_num}-HB) Active PLC Connection",end='\r')
            counter += 1
            sleep_time.sleep(1)
        print_red(f'({machine_num}-HB) Heartbeat: kill_threads high or reset event set, restarting all threads')
        kill_threads.clear()
   
# END heartbeat

def main():
    config_info = read_config()  # Read configuration information
    machine_num = [str(machine_num) for machine_num in config_info['keyence_ip']][0]
    keyence_ip = config_info['keyence_ip'][machine_num]
    
    # Create an instance of the create_cycle class
    cycle_instance = create_cycle(machine_num, keyence_ip)
    
    main_thread = threading.Thread(target=cycle_instance.cycle, name=f"ROBOT_{machine_num}")
    heartbeat_thread = threading.Thread(target=heartbeat, args=[machine_num], name=f"{machine_num}_heartBeat")

    main_thread.start()
    heartbeat_thread.start()
    event.set()  # Signal threads to start
    main_thread.join() # Wait for main thread to exit
    heartbeat_thread.join() # Wait for heartbeat thread to exit

if __name__ == '__main__':
    while True:
        main()

