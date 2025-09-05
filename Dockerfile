# Use Ubuntu as base image
FROM ubuntu:latest

# Set environment variables to non-interactive (prevents prompts)
ENV DEBIAN_FRONTEND=noninteractive

# Update package list and install common tools
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    vim \
    git \
    python3 \
    python3-pip \
    nodejs \
    npm \
    htop \
    tree \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Create a working directory
WORKDIR /app

# Set default shell to bash
SHELL ["/bin/bash", "-c"]

# Default command when container starts
CMD ["/bin/bash"]
