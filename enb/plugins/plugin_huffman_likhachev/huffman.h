#ifndef HUFFMAN_H_INCLUDED
#define HUFFMAN_H_INCLUDED

/* Encoding functions */
/**
  * Generates Huffman tree for data from an input file and encodes using the Huffman algorithm
  * via the only Huffman tree
  * then writes Huffman tree & encoded data to an output file.
  *
  * Arguments: pointers to input & output file.
  */
void encode(FILE*, FILE*);

/**
  * Generates Huffman tree & Huffman table for data from an input file and encodes using the Huffman algorithm
  * via the Huffman table (pretty much faster with the same result)
  * then writes Huffman tree & encoded data to an output file.
  *
  * Arguments: pointers to input & output file.
  */
void encodeQuick(FILE*, FILE*);

/* Decoding functions */
/**
  * Reads Huffman tree from an input file & then use it to decode data from the file
  * then writes decoded input (except Huffman tree) to an output file.
  * Unexpected behaviour on non-encoded or encoded not by this program files.
  *
  * Arguments: pointers to input & output file.
  */
void decode(FILE*, FILE*);

/* E & D both */
/**
  * Makes an encoding or decoding (depending on the third argument) of any input from file.
  *
  * Arguments: (absolute or not) names of input & output files, mode.
  * Modes:
  *      0 means encoding;
  *      1 means decoding;
  *      2 means fast encoding;
  *    The results of 0 & 2 modes are all the same except the time.
  */
int doHuffman(char*, char*, int);

#endif // HUFFMAN_H_INCLUDED
