from difflib import SequenceMatcher
import re

JUNK_CHARS = ''.join((',', '.', ';', ':', '"', "'", '-', ')', '(', '[', ']', '{', '}', '?', '!'))

"""
    Get the differences between two sequences of text.
"""
def diff_text(paragraph1: str, paragraph2: str, print_result: bool=True):

    # Split them into words by whitespace, so we diff on words instead of letters:
    p1, p2 = paragraph1.split(), paragraph2.split()

    # For each word, there can be punctuation attached. We want to remove the punctuation,
    # -- so that the diff doesn't care about it --but, we also want to keep track of the original
    # words *with* punctuation, so we can reconstruct the sentence. 
    p1_orig, p2_orig = p1[:], p2[:]
    p1 = [_cleaned(word) for word in p1]
    p2 = [_cleaned(word) for word in p2]

    # Diff on words, using difflib:
    s = SequenceMatcher(None, p1, p2)
    opcodes = s.get_opcodes()

    # Print the diff with added words in green and removed words in red
    # if print_result is True:
    #     _print_diff_colored(p1, p2, opcodes)
    
    return opcodes

# def _print_diff_colored(p1, p2, opcodes):
#     formatted_paragraph = ""
#     for opcode in opcodes:
#         # (tag, i1, i2, j1, j2) = opcode
#         # print("%s paragraph1[%d:%d] (%s) paragraph2[%d:%d] (%s)" % (tag, i1, i2, ' '.join(p1[i1:i2]), j1, j2, ' '.join(p2[j1:j2])))

#         if opcode[0] == 'equal':
#             # No change in this segment, just add it to both formatted paragraphs
#             formatted_paragraph += ' '.join(p1[opcode[1]:opcode[2]])
#         elif opcode[0] == 'delete':
#             # This segment was removed in the second paragraph, color it red in the first paragraph
#             formatted_paragraph += " \033[31m" + ' '.join(p1[opcode[1]:opcode[2]]) + "\033[0m "
#         elif opcode[0] == 'replace':
#             # This segment was replaced in the first paragraph, color it red in the first paragraph and green in the second
#             formatted_paragraph += " (\033[33m" + ' '.join(p1[opcode[1]:opcode[2]]) + "\033[0m ->"
#             formatted_paragraph += "\033[34m" + ' '.join(p2[opcode[3]:opcode[4]]) + "\033[0m) "
#         elif opcode[0] == 'insert':
#             # This segment was added in the second paragraph, color it green in the second paragraph
#             formatted_paragraph += " \033[32m" + ' '.join(p2[opcode[3]:opcode[4]]) + "\033[0m "
#     print(formatted_paragraph)

def _cleaned(s: str) -> str: 
    if len(s) == 0: return s
    orig_s = s
    s = s.lower()
    s = s.translate(str.maketrans('', '', JUNK_CHARS))
    return s
