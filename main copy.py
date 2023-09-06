
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
import inspect
import datetime
current_frame = inspect.currentframe()
frame_info = inspect.getframeinfo(current_frame)
path = frame_info.filename
filename = path.split("/")[-1]
today = datetime.date.today().strftime("%a-%b-%d-%Y")
now = datetime.datetime.now().strftime("%I:%M:%S.%f")[:-3]
logger = logging.getLogger(filename)
logger.setLevel(logging.DEBUG)
log_filename = f"{today}_MAIN.log"  # Include filename in the log name
handler = logging.FileHandler(log_filename)
formatter = logging.Formatter(f"{now} - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False
handler.close()
logger.removeHandler(handler)
#########################################################
spec_map = {}
event = threading.Event()
kill_threads = threading.Event()
part_program = 0
def print_green(message:str)->None:
    logger.debug(message)
    print(Fore.GREEN + f"{message}\n" + Style.RESET_ALL)
def print_blue(message:str)->None:
    logger.info(message)
    print(Fore.BLUE + f"{message}" + Style.RESET_ALL)
def print_yellow(message:str)->None:
    logger.info(message)
    print(Fore.YELLOW + f"{message}" + Style.RESET_ALL)
def print_red(message:str)->None:
    logger.critical(message)
    print(Fore.RED + f"{message}" + Style.RESET_ALL)
def read_config()->dict:
    with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
        config_data = config_file.read()
        config_vars = json.loads(config_data)
        return config_vars
class cycler:
    def __init__(self, machine_num, keyence_ip):   
        self.self = self
        self.machine_num = machine_num
        self.keyence_ip = keyence_ip
        self.current_stage = 0
    def cycle(self, machine_num, keyence_ip,reset_events):
        kill_threads.clear()
        event.wait()
        time.sleep(.05)
        config_info = read_config()
        print_blue(f'({machine_num}) Sequence Started\n({machine_num}) Connecting to PLC at {config_info["plc_ip"]}\n({machine_num}) Connected to Keyence at {keyence_ip}\n')
        scan_duration = 0 # keeping track of scan time in MS
        with LogixDriver(config_info['plc_ip']) as plc: #context manager for plc connection, currently resetting connection after ~24 hrs to avoid issues
            print_green(f'({machine_num}) ...PLC Connection Successful...\n')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Keyence socket connections
            sock.connect((keyence_ip, 8500))
           # setKeyenceRunMode(machine_num, sock)
            write_plc_fault_flush(plc,machine_num) # Fault Codes and raise ready
            connection_timer = datetime.datetime.now() #reset connection timer
            while(True):
                if(kill_threads.is_set()): #check reset at beginning of cycle
                    print_red(f'({machine_num}) kill_threads detected at cycle start! Restarting threads...\n')
                    break
                #spec_map = check_keyene_spec(sock, spec_map)
                reset_check = get_status_info(machine_num, plc)[0] #get part type and reset check from PLC
                if (reset_check[config_info['tags']['Reset']][1]):
                    self.current_stage = 0
                    reset_plc_tags(plc, machine_num,'type_one')
                    # kill_threads.set()
                    current_thread = threading.current_thread()
                    if current_thread in reset_events:
                        reset_events[current_thread].set()          
                if(self.current_stage == 0):
                    start_stage_zero(machine_num, plc, sock, self.current_stage) #stage 0 function
                    while(tag_data[config_info['tags']['LoadProgram']][1] != True): #Looping until LOAD PROGRAM goes high  # Data from PLC is only valid while LOAD_PROGRAM is low
                        if (kill_threads.is_set() or reset_events[threading.current_thread().name].is_set()): #check for reset at beginning of cycle
                            print_red(f'({machine_num})[STAGE:{self.current_stage}]  kill_threads detected while waiting for LOAD! Restarting threads...\n')
                            break
                        tag_data = read_plc_dict(plc, machine_num) #continuous full PLC read
                        reset_check = read_plc_single(plc, machine_num, 'Reset') #single plc tag read
                        if (reset_check[config_info['tags']['Reset']][1] == True):
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num,'type_one')
                            # kill_threads.set()
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(.050) # 5ms pause between reads
                    if (kill_threads.is_set() or reset_events[threading.current_thread().name].is_set()): #check for reset at beginning of cycle
                        break
                    print_green(f'({machine_num}) PLC(LOAD_PROGRAM) activated. Retrieving part data and program number...') # Once PLC(LOAD_PROGRAM) goes high, mirror data and set Phoenix(READY) high, signifies end of "loading" process
                    swap_check, part_program, part_type = stage_zero_preLoad(machine_num, plc, sock).values()
                    if swap_check == 0: # reset threads if invalid part type
                        # kill_threads.set()
                        current_thread = threading.current_thread()
                        if current_thread in reset_events:
                                reset_events[current_thread].set()
                    part_type = tag_data[config_info['tags']['PartType']][1]
                    print_blue(f'({machine_num})[STAGE:0] PRE-LOAD: Part Type({part_type})')
                    keyence_string = keyence_string_generator(machine_num, part_type, tag_data, sock, config_info) #building out external Keyence string for scan file naming
                    if keyence_string == 'ERROR':
                        # kill_threads.set()
                        current_thread = threading.current_thread()
                        if current_thread in reset_events:
                                reset_events[current_thread].set()
                    stage_zero_load(plc, sock, machine_num, tag_data) 
                    self.current_stage += 1 #increment current stage to proceed forward
                elif self.current_stage == 1:
                    print_yellow(f'({machine_num})[STAGE:1] Waiting for START_PROGRAM...\n')
                    while not tag_data[config_info['tags']['StartProgram']][1]: #looping until PLC(START_PROGRAM) goes high
                        if (kill_threads.is_set() or reset_events[threading.current_thread().name].is_set()): #check for reset at beginning of cycle
                            print_red(f'({machine_num}) kill_threads detected while waiting for START!\n...Restarting threads...\n') 
                            break
                        tag_data = read_plc_dict(plc, machine_num) #continuous PLC read
                        if tag_data[config_info['tags']['Reset']][1]: #check for reset during cycle
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num, 'type_two') # type_two reset for stage 1
                            if threading.current_thread() in reset_events:
                                reset_events[threading.current_thread()].set()
                        time.sleep(0.050)
                    print_green(f'({machine_num})[STAGE:1] PLC(START_PROGRAM) activated!\n')
                    exe_time,tag_data,start_trigger_timer = stage_one_trigger(plc, sock, machine_num, tag_data).values()
                    if (exe_time > 3000): # measure time it took to trigger keyence, if greater than 3 seconds, set fault
                        write_plc_fault(plc, machine_num, 2)
                    scan_duration,exe_time,tag_data= stage_one_post_trigger(plc, sock, machine_num, tag_data, start_trigger_timer).values()
                    if exe_time > 3000:
                        write_plc_fault(plc, machine_num, 3)

                    end_stage_one(plc, machine_num, sock, tag_data, scan_duration, keyence_string, part_type, part_program)
                    print_green(f'({machine_num})[STAGE:1] Complete!\n')
                    self.current_stage += 1
                elif self.current_stage == 2:  # Final Stage, reset to Stage 0 once PLC(END_PROGRAM) and PHOENIX(DONE) have been set low
                    write_plc_single(plc, machine_num, 'Done', True)
                    print_yellow(f'({machine_num})[STAGE:2] Waiting for PLC(ENDPROGRAM)\n')
                    while not tag_data[config_info['tags']['EndProgram']][1]:
                        if kill_threads.is_set() or reset_events[threading.current_thread().name].is_set():
                            print_red(f'({machine_num}) kill_threads detected while waiting for ENDPROGRAM! Restarting threads...\n')
                            break
                        tag_data = read_plc_dict(plc, machine_num)  # continuous PLC read
                        if tag_data[config_info['tags']['Reset']][1]:
                            print_yellow(f'({machine_num}) (StartProgram Check) Reset Detected! Setting back to Stage 0...\n')
                            self.current_stage = 0
                            reset_plc_tags(plc, machine_num, 'type_two')  # type_two reset for stage 2
                            current_thread = threading.current_thread()
                            if current_thread in reset_events:
                                reset_events[current_thread].set()
                        time.sleep(0.050)  # 5ms pause between reads
                    reset_toEnd_cycle(plc, machine_num, sock)  # reset PLC tags to end cycle
                    self.current_stage = 0  # cycle complete, reset to stage 0
                if abs(datetime.datetime.now() - connection_timer).total_seconds() > 86400:
                    print_red(f'({machine_num}) Connection reset detected! restarting threads...\n')
                    connection_timer = datetime.datetime.now()
                    current_thread = threading.current_thread()
                    if current_thread in reset_events:
                        reset_events[current_thread].set()
                if (kill_threads.is_set() or reset_events[threading.current_thread().name].is_set()): #check for reset at beginning of cycle
                    print_red(f'({machine_num}) kill_threads detected at cycle end! Restarting threads...\n')
                    break  # Kill thread if global is set True for any reason
                time.sleep(0.005)  # artificial loop timer
#END class Cycler
def heartbeat(machine_num, reset_event): #sets PLC(Heartbeat) high every second to verify we're still running and communicating
    config_info = read_config()
    def write_heartbeat(plc, machine_num):
        try:
            write_plc_single(plc, machine_num, 'HeartBeat', True)
        except Exception as error:
            print_red(f'({machine_num}) Exception in Heartbeat {error}')
            reset_event.set()
    with LogixDriver(config_info['plc_ip']) as plc:
        print_yellow(f'({machine_num}) Heartbeat thread connected to PLC. Writing \'Heartbeat\' high every 1 second\n')
        counter = 0
        while not (kill_threads.is_set() or reset_event.is_set()):
            write_heartbeat(plc, machine_num)
            if (counter % 200) == 0:
                print(f"({machine_num}) Active PLC Connection", end='\r')
            counter += 1
            time.sleep(1)
        print_red(f'({machine_num}) Heartbeat: kill_threads high or reset event set, restarting all threads')
# END heartbeat
def main():
    config_info = read_config()  # Read configuration information
    cycle_threads = []  # Store created cycle threads
    heartbeat_threads = []  # Store created heartbeat threads
    reset_events = {}  # Store reset events for each cycle thread
    for machine_num in list(config_info['mnKeyenceIP'].keys()):  # Loop through machines in config
        ip = config_info['mnKeyenceIP'][machine_num]
        cycle_object = cycler(machine_num, ip)
        cycle_thread = threading.Thread(target=cycle_object.cycle, args=[machine_num, ip, reset_events], name=f"machine_{machine_num}")
        reset_events[cycle_thread] = threading.Event()
        cycle_thread.start()
        cycle_threads.append(cycle_thread)
        heartbeat_thread = threading.Thread(target=heartbeat, args=[machine_num, reset_events], name=f"{machine_num}_heartBeat")
        heartbeat_thread.start()
        heartbeat_threads.append(heartbeat_thread) 
    event.set()  # Signal threads to start
    for cycle_thread, heartbeat_thread in zip(cycle_threads, heartbeat_threads):
        cycle_thread.join()
        reset_event = reset_events[cycle_thread]
        reset_event.set()  # Signal cycle thread to reset
        heartbeat_thread.join()
        cycle_object = cycle_threads.pop(0)
        new_cycle_thread = threading.Thread(target=cycle_object.cycle, args=[machine_num, ip, reset_events], name=f"machine_{machine_num}")
        cycle_threads.append(cycle_object)
        new_cycle_thread.start()
    for reset_event in reset_events.values():
        reset_event.clear()  # Clear reset events
#END 'main'
if __name__ == '__main__':
    while(True):
        main()
