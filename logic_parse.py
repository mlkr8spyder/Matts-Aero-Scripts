import re

def extract_phrases_from_brackets(file_path):
    with open(file_path, 'r') as file:
        text = file.read()
    
    # Regular expression to find phrases within brackets
    pattern = re.compile(r'\[(.*?)\]')
    matches = pattern.findall(text)
    
    # Remove duplicates by converting the list to a set and back to a list
    unique_phrases = list(set(matches))
    
    return unique_phrases

# Example usage
file_path = 'your_file.txt'  # Replace with the path to your text file
phrases = extract_phrases_from_brackets(file_path)
print(phrases)