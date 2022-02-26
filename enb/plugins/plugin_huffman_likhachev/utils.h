#ifndef UTILS_H_INCLUDED
#define UTILS_H_INCLUDED

/**
  * For internal use (sets the buffer counter).
  *
  */
void setCount(int);

/**
  * For internal use (returns value of the buffer counter).
  *
  */
int getCount();

/**
  * Reads one bit from file.
  *
  * Args: pointer to file.
  */
int readBit(FILE*);

/**
  * Reads 8 bits from file.
  *
  * Args: pointer to file.
  */
int readByte(FILE*);

/**
  * Writes one bit to file.
  *
  * Args: pointer to file, int 0 or 1 appropriate to bit value.
  */
void writeBit(FILE*, int);

/**
  * Writes specified number of bits to file.
  *
  * Args: pointer to file, sequence of bits in long, number of bits.
  */
void writeCode(FILE*, long, int);

/**
  * Finds max element of integer array and index of that element.
  *
  * Args: int array, array's size, pointer to int (to write index of max element).
  */
char findMax(int*, int, int*);

/**
  * Returns a specified bit of specified byte (as characters '0' and '1').
  *
  * Args: byte, offset (from right border).
  */
char getBit(unsigned char, int);

/**
  * Reads 4 bytes of integer from file.
  *
  * Args: pointer to file.
  */
int readInt(FILE*);

/**
  * Writes 4 bytes of integer to file.
  *
  * Args: pointer to file, integer number.
  */
void writeInt(FILE*, int);

/**
  * Converts code from string representation to long.
  *
  * Args: Code of a symbol as char sequence.
  */
long convertCode(char*);

#endif // UTILS_H_INCLUDED
