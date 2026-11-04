@echo off
title Sistema POS - Gestion Comercial
cd /d %~dp0
echo Iniciando el Sistema POS, por favor espere...
start http://localhost:8501
streamlit run app.py
pause