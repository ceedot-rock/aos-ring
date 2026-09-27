# Reference container build. The live Fly deploy uses the Machines API
# with server.py + optical_mem.py embedded in the machine config instead.
FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py optical_mem.py ./
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "server.py"]
