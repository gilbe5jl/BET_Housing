# BlankMiddleMan
#PLC - Keyence Automation

To run the program, simply open and execute the __main__.py file.

The __main__ file runs multiple Python files in the same directory as separate processes.

The robot_*.py files represents the control logic for a robot, keyence controller and Allen-Bradley PLC, referred to as "ROBOT *." It's designed to execute various stages of a operation while monitoring and managing connections to a Programmable Logic Controller (PLC) and a Keyence device. 

1. **Purpose**: This code controls the operation and manages communication with a PLC and a Keyence device for industrial automation tasks.

2. **Structure**: The code is organized into several modules, including `tag_lists.py`, `plc_utils.py`, `keyence_utils.py`, and others, to maintain modularity.

3. **Configuration**: It reads configuration data from a JSON file (`config_r*.json`) to obtain settings for the operation, including IP addresses and PLC tags.

4. **Multithreading**: The code uses Python's threading module to execute various stages of the robot's operation concurrently.

5. **Error Handling**: It incorporates error-handling mechanisms to detect issues like PLC and Keyence device connection timeouts and responds appropriately.

6. **Heartbeat Function**: A heartbeat function is implemented to ensure continuous communication with the PLC, restarting threads if necessary.

7. **Stages**: The code orchestrates the operations through different stages, such as loading, triggering, and completing tasks while monitoring PLC and Keyence device status.

8. **Usage**: To run the code, execute the `__main__.py` file, which launches the robot's operation and handles multithreading. The code is designed for industrial automation scenarios and can be adapted to specific tasks by modifying the configuration and logic within the various modules.

