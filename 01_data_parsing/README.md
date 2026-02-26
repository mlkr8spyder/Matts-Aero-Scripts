# Data Parsing Tools

Utility scripts for extracting and parsing structured data from text files.

## Files

- **logic_parse.py** - Extract phrases from text files using regex (finds content within brackets `[...]`)
- **material_parse.py** - Parse material property data organized by location and part number
- **thickness_parse.py** - Parse thickness measurements and their associated part numbers

## Usage Example

```python
from material_parse import parse_file_with_materials

data = parse_file_with_materials('material.txt')
# Returns dict: {location: [(part_number, material), ...]}
```

## Input Format

Expected structure in text files:
```
LOCATION_NAME
PART_NUMBER_1
MaterialName
PART_NUMBER_2
MaterialName
```

## Use Case

Preprocessing raw structured text files into Python data structures for further analysis or database import.
