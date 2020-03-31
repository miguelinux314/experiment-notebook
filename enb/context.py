#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module to keep track of contexts
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "13/11/2019"

import math


class ValueCounter:
    """Keep tally of a given general context with prefixed allowed values
    """

    def __init__(self, allowed_values, context=None):
        """
        :param allowed_values: list of values allowed in add()
        :param context: None, or a reference to the context for which self is a counter
        """
        self.context = context
        self.value_to_count = {v: 0 for v in allowed_values}

    @property
    def value_to_relfreq(self):
        """Get a dictionary indexed by tracked value, and values being the relative
        frequency of each of them. Note that this function only takes into account
        samples counted in this instance (i.e., conditioned to the current context).
        """
        vc = self.value_to_count
        total_sum = sum(vc.values())
        return {value: count / total_sum for value, count in vc.items()}

    def add(self, value):
        """Tally one more of the given value, which should be in the
        list of allowed values
        """
        try:
            self.value_to_count[value] += 1
        except KeyError:
            print(f"Value {value} not in {self.value_to_count.keys()}")

    @property
    def allowed_values(self):
        return sorted(list(self.value_to_count.keys()))

    @property
    def total_count(self):
        return sum(self.value_to_count.values())

    @property
    def entropy(self):
        """Get the entropy fo this context (without taking its relative probability
        among other contexts into account)
        """
        total_sum = sum(self.value_to_count.values())
        if total_sum == 0:
            raise ValueError(f"Cannot compute entropy of context {self}: total count is 0")
        probabilities = [c / total_sum for c in self.value_to_count.values()]
        assert abs(sum(probabilities) - 1) < 1e-12, sum(probabilities)
        return - sum(p * math.log2(p) if p != 0 else 0 for p in probabilities)

    def __str__(self):
        return f"{self.__class__.__name__}" \
               + (f"(ctx={self.context})" if self.context else "") \
               + f"({sorted(self.value_to_count.items())})"


class ContextGroup:
    def __init__(self, allowed_values, allowed_contexts):
        allowed_contexts = [None] if allowed_contexts is None else allowed_contexts
        assert len(allowed_contexts) >= 1
        self.context_to_counter = {c: ValueCounter(allowed_values=allowed_values)
                                   for c in allowed_contexts}

    def add(self, context, value):
        """Add tally of a single sample value at a given context
        """
        self.context_to_counter[context].add(value)

    @property
    def entropy(self):
        context_to_prob = {context: counter.total_count
                           for context, counter in self.context_to_counter.items()}
        context_to_prob = {context: count / sum(context_to_prob.values())
                           for context, count in context_to_prob.items()
                           if count > 0}
        if not context_to_prob:
            raise ValueError(f"Cannot compute entropy for group {self}: no value was added")
        assert abs(sum(context_to_prob.values()) - 1) < 1e-10, sum(context_to_prob.values())

        return sum(context_to_prob[context] * counter.entropy
                   for context, counter in self.context_to_counter.items()
                   if counter.total_count > 0)

    @property
    def context_count_by_index(self):
        """Get the number of samples counted in each context.
        Context indices are computed assuming that contexts are given
        by the context bit (single-bit contexts)
        from MSB to LSB (for multi-bit contexts)
        """

        cc_by_index = {}
        sorted_contexts = sorted(self.context_to_counter.keys())
        for context, counter in self.context_to_counter.items():
            cc_by_index[sorted_contexts.index(context)] = counter.total_count
        return cc_by_index

    @property
    def context_relfreq_by_index(self):
        cc_by_index = self.context_count_by_index
        total_sum = sum(cc_by_index.values())
        return {index: cc / total_sum for index, cc in cc_by_index.items()}

    @property
    def allowed_contexts(self):
        return sorted(list(self.context_to_counter.keys()))

    @property
    def allowed_values(self):
        return list(self.context_to_counter.values())[0].allowed_values
