# -*- coding: utf-8 -*-
"""
Created on Mon Sep  7 07:09:04 2020

@author: Duong Hung
"""

import sys
def hello(a, b):
    print("hello and that's your sum:")
    sum = a+b
    print(sum)

if __name__== "__main__":
    hello(int(sys.argv[1]), int(sys.argv[2]))