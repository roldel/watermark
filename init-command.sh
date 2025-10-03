# Initialize docker container

sudo docker run -it -v $(pwd):/script -w /script python:slim bash

# apt dependencies

apt update && apt install -y ghostscript libjpeg-dev zlib1g-dev

# python dependencies

pip install pillow img2pdf PyPDF2 reportlab
