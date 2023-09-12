import unittest
from unittest.mock import Mock
from plc_utils import * # Replace 'your_module' with the actual module name where the function is defined



def test_read_plc_dict():
    # Create a mock LogixDriver and define its behavior
    mock_plc_driver = Mock()
    machine_number = "3"
    
    # Define sample output tags and their values
    sample_output_tags = ["Tag1", "Tag2", "Tag3"]
    sample_values = [True, 42, "SampleData"]
    
    # Mock the read method of LogixDriver to return sample data
    mock_plc_driver.read.return_value = [
        Mock(tag=f"Program:Prefix.O.{tag}", value=value, type=None, error=None)
        for tag, value in zip(sample_output_tags, sample_values)
    ]
    
    # Define expected result dictionary
    expected_result = {
        "Tag1": (f"Program:Prefix.O.Tag1", True, None, None),
        "Tag2": (f"Program:Prefix.O.Tag2", 42, None, None),
        "Tag3": (f"Program:Prefix.O.Tag3", "SampleData", None, None)
    }
    
    # Call the function with the mock LogixDriver
    result = read_plc_dict(mock_plc_driver, machine_number)
    
    # Assert that the result matches the expected dictionary
    # assertEqual(result, expected_result)
    return result


def test_write_plc_successful():
    # Ensure the function works when all tags are found in results
    mock_plc = unittest.mock.MagicMock()
    machine_num = "3"
    results = {
        "Tag1": (None, 42, None, None),
        "Tag2": (None, 123, None, None),
        "PART_TYPE": (None, "SampleData", None, None),
        "PART_PROGRAM": (None, "SampleData", None, None),
        "SCAN_NUMBER": (None, 123, None, None),
        "PUN": (None, 123, None, None),
        "MODULE": (None, 123, None, None),
        "PLANT_CODE": (None, 123, None, None),
        "TIMESTAMP_MONTH": (None, 123, None, None),
        "TIMESTAMP_DAY": (None, 123, None, None),
        "TIMESTAMP_HOUR": (None, 123, None, None),
        "TIMESTAMP_MINUTE": (None, 123, None, None),
        "TIMESTAMP_SECOND": (None, 123, None, None),
        "TIMESTAMP_YEAR": (None, 123, None, None),

        # Add more tags as needed for testing
    }
    assert write_plc(mock_plc, machine_num, results) is None

print(test_read_plc_dict())
print(test_write_plc_successful())