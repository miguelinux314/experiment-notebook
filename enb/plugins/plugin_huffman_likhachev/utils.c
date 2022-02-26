#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "utils.h"

/* Buffer */
unsigned char buffer = 0;
int count = 0;

void setCount(int);
int getCount();
int readBit(FILE*);
int readByte(FILE*);
void writeBit(FILE*, int);
void writeCode(FILE*, long, int);

char findMax(int*, int, int*);
char getBit(unsigned char, int);
int readInt(FILE*);
void writeInt(FILE*, int);
long convertCode(char*);

/* Implementations */

void setCount(int v)
{
  count = v;
}

int getCount()
{
  return count;
}

int readBit(FILE* in)
{
  int res, readed;
  if (count == 0)
    {
      readed = fread(&buffer, 1, 1, in);
      count = readed * 8;
    }
  res = buffer & 0x80; // 0x80 == _1_0000000
  buffer = buffer << 1;
  count--;
  return res;
}

int readByte(FILE* in)
{
  int i, res = 0;
  for (i = 0; i < 8; i++)
    {
      res = res << 1;
      if (readBit(in))
        {
          res |= 1;
        }
    }
  return res;
}

void writeBit(FILE* out, int value)
{
  buffer = buffer << 1;
  if (value)
    {
      buffer |= 1;
    }
  count++;
  if (count == 8)
    {
      fwrite(&buffer, 1, 1, out);
      count = 0;
    }
}

void writeCode(FILE* out, long code, int length)
{
  size_t i;
  long mask;
  for (i = length; i > 0; i--)
    {
      mask = 1 << (i - 1);
      writeBit(out, code & mask);
    }
}

char findMax(int *array, int size, int *frequency)
{
  int i, max = array[0], maxIndex = 0;
  for (i = 0; i < size; i++)
    {
      if (array[i] > max)
        {
          max = array[i];
          maxIndex = i;
        }
    }
  array[maxIndex] = 0; // значение обнуляется, чтобы один и тот же символ не встречался более одного раза
  if (max != 0) *frequency = max;
  return (char) maxIndex;
}

char getBit(unsigned char byte, int offset)
{
  return (((byte >> offset) & 0x1) == 0x1) ? '1' : '0';
}

int readInt(FILE *file)
{
  int value;
  fread(&value, sizeof(int), 1, file);
  return value;
}

void writeInt(FILE *file, int value)
{
  fwrite(&value, sizeof(int), 1, file);
}

long convertCode(char *code)
{
  size_t i;
  long res = 0;
  for (i = 0; i < strlen(code); i++)
    {
      res = res << 1;
      if (code[i] == '1')
        {
          res |= 1;
        }
    }
  return res;
}
