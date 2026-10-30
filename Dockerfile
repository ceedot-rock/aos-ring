# Container build with the persistence layer on: AOS_DATA_DIR points at
# the /data volume, so ring state snapshots there and survives restarts.
# (The live Fly deploy uses the Machines API with server.py +
# optical_mem.py embedded in the machine config instead, still volatile.)
FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py optical_mem.py ./
ENV PORT=8080
ENV AOS_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8080
CMD ["python3", "server.py"]
