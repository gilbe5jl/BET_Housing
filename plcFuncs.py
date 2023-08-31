from pycomm3 import LogixDriver
from pycomm3.tag import Tag
import tagLists
import sys
import os
import json
import MiddleManLogger as mml

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
    out_tags = tagLists.OTagList()
    prefix = f"Program:{config_info['mnTagPrefix'][machine_number]}.O."
    readList = [f"{prefix}{tag}" for tag in out_tags] # list comprehension of tags to read
    # read() method is called on the plc_driver object, passing in the list of tags to read as an argument.
    resultsList = plc_driver.read(*readList) # splat-read: tag, value, type, error
    #The result object returned by read() contains value, type, and error properties, which are used to populate the values of the tuples in the resulting dictionary.
    readDict = {}
    #generating list of tag names, ONLY end of the full tag name
    for result in resultsList:
        key = result.tag.split(".")[-1]
        readDict[key] = (result.tag, result.value, result.type, result.error)
    return readDict
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
    Itags = tagLists.ITagList(1)
    for i in Itags:
        try:
            tag = prefix + i
            value = results[i][1]
            plc.write((tag, value))
        except KeyError as error:
            mml.log("e",True,f'({machine_num}) PLC write ERROR! KeyError:{error}')
        except Exception as error:
            mml.log("e",True,f'({machine_num}) PLC write ERROR! Exception:{str(error)}')
#END write_plc

# Flushes PLC data mirroring tags (to 0)
def write_plc_flush(plc:LogixDriver, machine_num:str) -> None:
    prefix = 'Program:' + config_info['mnTagPrefix'][machine_num] + '.I.'
    default = {
        'PUN{64}': [0] * 64
    }
    Itags = tagLists.ITagList(2)
    for tag in Itags:
        try:
            if tag == 'PUN':
                plc.write((prefix + tag, default['PUN{64}']))
            else:
                plc.write((prefix + tag, 0))
        except Exception as error:
            mml.log("e",True,f'({machine_num}) PLC flush ERROR! Exception:{str(error)}')
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
   
    
    plc.write(('Program:' + config_info['mnTagPrefix'][machine_num] + '.I.' + config_info['tags'][tag_name], tag_val))
    return


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
        print(f'({machine_num}) {error} ERROR READING PLC TAG {tag_name}')
    return read_dict # Return the dictionary of tag values
#END read_plc_singles
    

def int_array_to_str(int_array:list) -> str:
    """
    Convert a list of integers to a string of ASCII characters (PLC int-arrays into ASCII string for OPC)
    :param int_array: A list of integers to be converted to a string
    :return: A string of ASCII characters
    """
    # List comprehension to convert each integer to its corresponding ASCII character. Then join the characters into a single string
    ret = ''.join(chr(i) for i in int_array)
    return ret
#END int_array_to_str
