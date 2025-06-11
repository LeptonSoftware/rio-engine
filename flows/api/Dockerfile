# Use the official tiangolo/uvicorn-gunicorn-fastapi image as the base image
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /deps

RUN apt-get update \
    && apt-get install -y build-essential cmake python3-dev python3-numpy libproj-dev libsqlite3-dev libtiff-dev libjpeg-dev libpng-dev libgeos-dev libcurl4-gnutls-dev wget sudo libpq-dev imagemagick \
    # Add Oracle Instant Client dependencies
    && apt-get install -y libaio1 unzip p7zip-full unar tar\
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
    

# Step 4: Install GDAL from source with PostgreSQL support
RUN wget https://github.com/OSGeo/gdal/releases/download/v3.9.3/gdal-3.9.3.tar.gz \
    && tar -xvf gdal-3.9.3.tar.gz \
    && cd gdal-3.9.3/ \
    && mkdir build \
    && cd build/ \
    && cmake .. -DGDAL_BUILD_OPTIONAL_DRIVERS=ON -DGDAL_USE_PYTHON=ON -DGDAL_ENABLE_POSTGRES=ON \
    && make -j$(nproc) \
    && sudo make install \
    && sudo ldconfig

# Set the GDAL library path
ENV LD_LIBRARY_PATH="/deps/gdal-3.9.3/build:$LD_LIBRARY_PATH"

# Set the working directory inside the container
WORKDIR /app

# Copy requirements.txt to the /app directory in the image
COPY requirements.txt /app

RUN pip install -r requirements.txt
RUN gdalinfo --version
RUN ogrinfo --formats | grep -i postgres

COPY . /app