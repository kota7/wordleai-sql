#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tempfile import TemporaryDirectory
import streamlit as st
from wordleaisql import __version__ as wordleaisql_version

def main():
    with st.sidebar:
        st.selectbox("", ("Solver", "Challenge", "Play"))
        st.write("wordleaisql v%s" % wordleaisql_version)
    st.write("Hellow world!")
    st.markdown("**Hellow** *world*!")

if __name__ == "__main__":
    main()