============
Introduction
============

Overview
------------------------

grg-psse2grg is a python package for translating PSSE and GRG network data files.

The primary entry point of the library is :class:`grg_psse2grg.io` module, which contains the methods for bi-directional translation.


Installation
------------------------

Simply run::

    pip install grg-psse2grg


Testing
------------------------

grg-psse2grg is designed to be a library that supports other software.  
It is not immediately useful from the terminal.
However, you can test the parsing functionality from the command line with:: 

    python -m grg_psse2grg.io <path to PSSE or GRG case file>

If this command is successful, you will see a translated plain text version of the translated network data printed to the terminal.


