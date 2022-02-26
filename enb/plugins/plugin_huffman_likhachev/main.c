#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <locale.h>
#include "huffman.h"

const char *messages[] =
{
  "Input successfully processed.\n",
  "Can't open input file to read.\n",
  "Can't open output file to write.\n"
};

int main(int argc, char *argv[])
{
  int mode;
  char *infilename;
  char *outfilename;
  
  if (argc != 4) {
      fprintf(stderr, "Invalid number of arguments.\nSyntax: %s <mode(e,eq,d)> <input_file> <output_file>\n", argv[0]);
      return -1;
  }
  mode = (argc > 1) ? (!strcmp(argv[1], "e") ? 0 : (!strcmp(argv[1], "qe") ? 2 : 1)) : 0;
  infilename = argv[2];
  outfilename = argv[3];
  setlocale(LC_ALL, "");
  printf("Input file: %s\n", infilename);
  printf("Output file: %s\n", outfilename);
  printf("Mode: %s\n\n", mode == 0 || mode == 2 ? "encoding" : "decoding");

  printf("%s", messages[doHuffman(infilename, outfilename, mode)]);

  return 0;
}
