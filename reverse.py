import sys

def reverse_file(input_file, output_file):
    # Read lines from input file
    with open(input_file, "r") as f:
        lines = f.readlines()

    # Count characters and words
    char_count = sum(len(line) for line in lines)
    word_count = sum(len(line.split()) for line in lines)

    # Reverse the lines
    reversed_lines = lines[::-1]

    # Write to output file
    with open(output_file, "w") as f:
        for line in reversed_lines:
            f.write(line)

    # Print counts
    print("Total Characters:", char_count)
    print("Total Words:", word_count)


# Example usage:
# reverse_file("file.txt", "result.txt")

# If using command line arguments:
if len(sys.argv) == 3:
    reverse_file(sys.argv[1], sys.argv[2])
