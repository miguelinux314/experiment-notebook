/* 
 * Reference Huffman coding
 * 
 * Copyright (c) Project Nayuki
 * MIT License. See readme file.
 * https://www.nayuki.io/page/reference-huffman-coding
 */

#include <stdexcept>
#include "HuffmanCoder.hpp"


HuffmanDecoder::HuffmanDecoder(BitInputStream &in) :
	input(in) {}


int HuffmanDecoder::read() {
	if (codeTree == nullptr)
		throw std::logic_error("Code tree is null");
	
	const InternalNode *currentNode = &codeTree->root;
	while (true) {
		int temp = input.readNoEof();
		const Node *nextNode;
		if      (temp == 0) nextNode = currentNode->leftChild .get();
		else if (temp == 1) nextNode = currentNode->rightChild.get();
		else throw std::logic_error("Assertion error: Invalid value from readNoEof()");
		
		if (dynamic_cast<const Leaf*>(nextNode) != nullptr)
			return dynamic_cast<const Leaf*>(nextNode)->symbol;
		else if (dynamic_cast<const InternalNode*>(nextNode))
			currentNode = dynamic_cast<const InternalNode*>(nextNode);
		else
			throw std::logic_error("Assertion error: Illegal node type");
	}
}


HuffmanEncoder::HuffmanEncoder(BitOutputStream &out) :
	output(out) {}


void HuffmanEncoder::write(std::uint32_t symbol) {
	if (codeTree == nullptr)
		throw std::logic_error("Code tree is null");
	for (char b : codeTree->getCode(symbol))
		output.write(b);
}
