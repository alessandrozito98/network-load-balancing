# Load Balancing


## Description

A ryu program that send packets to the controller, and for each new connection, choose the lowest cost path, giving less weight to the unloaded connections. Finally it will upload a rule to the switch to send packets without using the controller.

## Authors

Fabio Mauri ([@cripty2001](https://github.com/cripty2001)) fabio6.mauri@mail.polimi.it

Luciano Oliva ([@OlivaLuciano](https://github.com/OlivaLuciano)) luciano1.oliva@mail.polimi.it

Alessandro Zito ([@alessandrozito98](https://github.com/alessandrozito98)) alessandro4.zito@mail.polimi.it

## Installation

Needs python3. See the Usage section to install all the dependencies.

## Configuration

### Usage

Clone this ([virtual machine](https://github.com/gverticale/sdn-vm-polimi)) and then, after installed the vm, clone this repo in the vm. Then in a bash console:

```bash
ryu-manager --observe-links path/to/folder/controller.py path/to/folder/flowmanager.py
``` 

## Credits
[Giacomo Verticale](https://github.com/gverticale/)'s repo.


This project was developed during the Software Defined Networking course at Polytechnic University of Milan. It has been evaluated 3/3 points more in the final mark of the exam.
