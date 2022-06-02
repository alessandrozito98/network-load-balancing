# Load Balancing


## Description

a ryu program that send packets to the controller, and for each new connection, choose the lowest cost path, giving less weight to the unloaded connections. Finally upload a rule to the switch to send packets without using the controller.

## Authors

887630 Fabio Mauri ([@cripty2001](https://github.com/cripty2001)) fabio6.mauri@mail.polimi.it

937677 Luciano Oliva ([@OlivaLuciano](https://github.com/OlivaLuciano)) luciano1.oliva@mail.polimi.it

890219 Alessandro Zito ([@alessandrozito98](https://github.com/alessandrozito98)) alessandro4.zito@mail.polimi.it

## Installation

Needs python3.

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install all the librabries.

```bash
pip3 install -r requirements.txt
```


## Configuration

### Usage

Clone this ([virtual machine](https://github.com/gverticale/sdn-vm-polimi)) and then, after installed the vm, clone this repo in the vm. Then in a bash console:

```bash
ryu-manager --observe-links path/to/folder/controller.py path/to/folder/flowmanager.py
``` 

## Credits
([Giacomo Verticale](https://github.com/gverticale/))'s repo.


This project was developed during the Software Defined Networking course at Polytechnic University of Milan. It has been evaluated 3/3 points more in the final mark of the exam.
