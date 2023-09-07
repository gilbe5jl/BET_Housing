from pycomm3 import LogixDriver
from pycomm3.tag import Tag
import tag_lists
import sys
import os
import json
from colorama import Fore, Style

#

def extract_machine_num(message):
    # Find the opening parenthesis and closing parenthesis in the message
    start_index = message.find('(')
    end_index = message.find(')')

    # Check if both parentheses are found
    if start_index != -1 and end_index != -1:
        # Extract the substring between the parentheses
        machine_num_str = message[start_index + 1:end_index]
        
        try:
            # Attempt to convert the extracted substring to an integer
            machine_num = int(machine_num_str)
            return machine_num
        except ValueError:
            # Handle the case where the substring cannot be converted to an integer
            return None

    return None  # Return None if the parentheses are not found
def print_color(message:str)->None:
    machine_num = str(extract_machine_num(message))
    if machine_num == '3':
        print_blue(message)
    elif machine_num == '4':
        print_green(message)
    elif machine_num == '5':
        print_yellow(message)


def print_green(message:str)->None:
    message = Fore.GREEN + f"{message}\n" + Style.RESET_ALL
    # logger.info(message)
    print(message)
def print_blue(message:str)->None:
    # logger.info(message)
    print(Fore.BLUE + f"{message}" + Style.RESET_ALL)
def print_yellow(message:str)->None:
    # logger.info(message)
    print(Fore.YELLOW + f"{message}" + Style.RESET_ALL)
def print_red(message:str)->None:
    # logger.critical(message)
    print(Fore.RED + f"{message}" + Style.RESET_ALL)

with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
    config_data = config_file.read()
    config_info = json.loads(config_data)


#single-shot read of all 'arrayOutTags' off PLC
def read_plc_dict(plc_driver:LogixDriver, machine_number:str):
    """
    Reads a list of tags from a PLC and returns a dictionary of the results.
    :param plc_driver: The LogixDriver object used to communicate with the PLC.
    :param machine_number: The machine number of the Keyence Controller.
    :return: A dictionary of the results of the read operation.
    """
    out_tags = tag_lists.output_tag_list()
    prefix = f"Program:{config_info['mnTagPrefix'][machine_number]}.O."
    readList = [f"{prefix}{tag}" for tag in out_tags] # list comprehension of tags to read
    # read() method is called on the plc_driver object, passing in the list of tags to read as an argument.
    results_list = plc_driver.read(*readList) # splat-read: tag, value, type, error
    #The result object returned by read() contains value, type, and error properties, which are used to populate the values of the tuples in the resulting dictionary.
    read_map = {}
    #generating list of tag names, ONLY end of the full tag name
    for result in results_list:
        key = result.tag.split(".")[-1]
        read_map[key] = (result.tag, result.value, result.type, result.error)
    return read_map
#END read_plc_dict

#Writing back to PLC to mirror data on LOAD
def write_plc(plc:LogixDriver, machine_num:str, results:dict) ->None:
    """
    Write data back to PLC to mirror data on LOAD
    :param plc: PLC driver object
    :param machine_num: machine number
    :param results: dictionary of tags and values
    :return: None
    """
    prefix = 'Program:' + config_info['mnTagPrefix'][machine_num] + '.I.'
    input_tags = tag_lists.input_tag_list(1)
    for i in input_tags:
        try:
            tag = prefix + i
            value = results[i][1]
            plc.write((tag, value))
        except KeyError as error:
            print_red(error)
            # mml.log("e",True,f'({machine_num}) PLC write ERROR! KeyError:{error}')
        except Exception as error:
            print_red(error)
            # mml.log("e",True,f'({machine_num}) PLC write ERROR! Exception:{str(error)}')
#END write_plc


def write_plc_fault_flush(plc:LogixDriver,machine_num:str)-> None:
    """
    clearing potential fault info when resetting
    :param plc: The LogixDriver object that is connected to the PLC system
    :param machine_num: The machine number of the Keyence Controller
    return none
    """
    print_color(f'({machine_num}) Flushing PLC(Result) tag data...\n')
    fault_tag_data = {
        'Faulted': False,
        'PhoenixFltCode': 0,
        'KeyenceFltCode': 0,
        'FaultStatus': 0,
        'Done': False,
        'Pass': False,
        'Busy': False,
        'Fail': False,
        'PartProgram': 0,
        'Ready': True,
    }
    for i,j in zip(fault_tag_data.keys(),fault_tag_data.values()):
        write_plc_single(plc, machine_num,i,j)

# Flushes PLC data mirroring tags (to 0)
def write_plc_flush(plc:LogixDriver, machine_num:str) -> None:
    prefix = 'Program:' + config_info['mnTagPrefix'][machine_num] + '.I.'
    default = {'PUN{64}': [0] * 64 }
    input_tags = tag_lists.input_tag_list(2)
    for tag in input_tags:
        try:
            if tag == 'PUN':
                plc.write((prefix + tag, default['PUN{64}']))
            else:
                plc.write((prefix + tag, 0))
        except Exception as error:
            print_red(error)
#END write_plc_flush


# Writes a single PLC tag
def write_plc_single(plc:LogixDriver, machine_num:str, tag_name:str, tag_val) -> None:
    """
    Write a single PLC tag to the PLC system
    :param plc: The LogixDriver object that is connected to the PLC system
    :param machine_num: The machine number of the Keyence Controller
    :param tag_name: The name of the PLC tag to be written
    :param tag_val: The value to be written to the PLC tag
    :return: None
    """
    # if tag_name != 'HeartBeat':
    #     print_color(f'({machine_num}) Setting PLC({tag_name}) to {tag_val}')
    plc.write(('Program:' + config_info['mnTagPrefix'][machine_num] + '.I.' + config_info['tags'][tag_name], tag_val))

def reset_plc_tags(plc: LogixDriver, machine_num: str,reset_type:str) -> None:
    """
    Reset multiple PLC tags to their default values.
    :param plc: The LogixDriver object that is connected to the PLC system
    :param machine_num: The machine number of the Keyence Controller
    :return: None
    """
    if reset_type == 'type_one':
        print_color(f'({machine_num}) Reset detected before loading. Resetting to Stage 0...')
        print_color(f'({machine_num}) Flushing PLC Fault Tags...\n')
        write_plc_flush(plc, machine_num)
        write_plc_single(plc, machine_num, 'Faulted', False)
        write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
        write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
        write_plc_single(plc, machine_num, 'FaultStatus', 0)
    elif reset_type == 'type_two':
        print_color(f'({machine_num}) Reset detected after loading. Resetting to Stage 0...')
        print_color(f'({machine_num}) Flushing PLC Fault Tags...\n')
        write_plc_flush(plc,machine_num)
        write_plc_single(plc, machine_num, 'Reset', False)
        write_plc_single(plc, machine_num, 'Faulted', False)
        write_plc_single(plc, machine_num, 'FaultStatus', 0)
        write_plc_single(plc, machine_num, 'PhoenixFltCode', 0)
        write_plc_single(plc, machine_num, 'KeyenceFltCode', 0)
    elif reset_type == 'type_three':
        write_plc_single(plc, machine_num, 'Done', False)
        write_plc_single(plc, machine_num, 'Pass', False)
        write_plc_single(plc, machine_num, 'Busy', False)
        write_plc_single(plc, machine_num, 'Fail', False)
        write_plc_single(plc, machine_num, 'Aborted', False)

def set_bool_tags(plc:LogixDriver, machine_num:str) -> None:
    print_color(f'({machine_num}) Setting Boolean Tags for Stage 0\n') #flag reset/beginning of timing diagram
    write_plc_single(plc, machine_num, 'Done', False)
    write_plc_single(plc, machine_num, 'Pass', False)
    write_plc_single(plc, machine_num, 'Busy', False)
    write_plc_single(plc, machine_num, 'Fail', False)
    write_plc_single(plc, machine_num, 'Ready', True)   

def read_plc_single(plc:LogixDriver, machine_num:str, tag_name:str) -> dict:
    """
    Read the specified PLC tags from the PLC system and return the results as a dictionary
    :param plc: The LogixDriver object that is connected to the PLC system
    :param machine_num: The machine number of the Keyence Controller
    :param tag_names: A string of the internal name of the PLC tag to be read
    :return: A dictionary of the tag value read from the PLC system
    """
    # Construct the prefix for the PLC tags for the specified machine number
    prefix = config_info['mnTagPrefix'][machine_num] + '.O.' ####################################################CHANGED TO .I. for testing 
    # Construct a list of the full tag names to be read from the PLC
    tag_name = f"Program:{prefix}{config_info['tags'][tag_name]}"
     #readList = [f"{prefix}{tag}" for tag in tag_names]
    # Read the current values of the tags from the PLC using the splat-read syntax, results stored in a list of Tag objects
    result_tag = plc.read(tag_name) # The Tag object contains the tag name, value, data type, and error status
    # Create a dictionary to store the tag values read from the PLC
    read_dict = {}
    # Generate a dictionary of tag values where the key is the last part of the tag name
    # This is done because the full tag name includes the prefix that we added, but we only
    # want to store the values by the tag name itself
 
    try:
        key = result_tag.tag.split(".")[-1]
        read_dict[key] = result_tag
    except Exception as error:
        print_color(f'({machine_num}) {error} ERROR READING PLC TAG {tag_name}')
    return read_dict # Return the dictionary of tag values
#END read_plc_singles
    

def int_array_to_str(int_array:list) -> str:
    """
    Convert a list of integers to a string of ASCII characters (PLC int-arrays into ASCII string for OPC)
    :param int_array: A list of integers to be converted to a string
    :return: A string of ASCII characters
    """
    # List comprehension to convert each integer to its corresponding ASCII character. Then join the characters into a single string
    string = ''.join(chr(i) for i in int_array)
    print_color(f"Converting PUN toString...\n{string}")
    return string
    
#END int_array_to_str
def flush_check_pass(plc:LogixDriver,tag_name:str)->None:
    plc.write((tag_name,0))
    
def write_plc_check_pass(plc:LogixDriver,machine_num:str,tag_name:str,tag_value)->None:
    plc.write((tag_name,tag_value))


def write_plc_fault(plc:LogixDriver,machine_num:str,fault_type:int)->None:
    if fault_type == 2:
        print_red(f'({machine_num}) Trigger Keyence timeout fault (longer than 3 seconds)! PhoenixFltCode : 2')
        write_plc_single(plc, machine_num, 'PhoenixFltCode', 2)
        write_plc_single(plc, machine_num, 'FaultStatus', 2)
        write_plc_single(plc, machine_num, 'Faulted', True)
    elif fault_type == 3:
        print_red(f'({machine_num}) TIMEOUT ERROR: Keyence not running (Execution time exceeded 3 seconds)\n\tPhoenixFltCode : 3\n')
        write_plc_single(plc, machine_num, 'PhoenixFltCode', 3)
        write_plc_single(plc, machine_num, 'FaultStatus', 3)
        write_plc_single(plc, machine_num, 'Faulted', True)