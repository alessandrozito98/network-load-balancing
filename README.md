# Load Balancing


## Description

Simulations of different electoral laws with the same dataset to see if there would be any changes in the composition of the parliament.

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

<!---
Description of the project can be found [here](https://github.com/alessandrozito98/Progetto_Reti_Logiche_2020/tree/master/Docs).

Specific document can be found [here](https://en.wikipedia.org/wiki/Histogram_equalization).

## Histogram Equalization 

The component required had to receive a 8-bit pixels of an image as input and calculate the new pixel value by following the specifications in "Histogram Equalitazion" method.

*This project has been developed as part of the "Reti Logiche" course at [Politecnico di Milano](https://www.polimi.it/).* It has been evaluated "30/30" cum Laude.

### Input Format
The program expects its input from stdio with the following format. It receives from RAM in the first two addressed the number of the rows and then columns. From the tird address, it receives the pixels values to convert.

***Example of the input stream:***
```
signal RAM: ram_type := (0 => std_logic_vector(to_unsigned(  2  , 8)), 
                         1 => std_logic_vector(to_unsigned(  2  , 8)), 
                         2 => std_logic_vector(to_unsigned(  46  , 8)),  
                         3 => std_logic_vector(to_unsigned(  131  , 8)), 
                         4 => std_logic_vector(to_unsigned(  62  , 8)), 
                         5 => std_logic_vector(to_unsigned(  89  , 8)), 
                         others => (others =>'0'));  
```
 
 ***Expected output***
```
0
255
64
72
```

### Testing Result

The testing platform was divided in public and private tests. Public tests can be found here. The results of some public tests is written in the final report.

However, i also tested my program using a test generator written by me and other students. The original repo can be found [here](https://github.com/davidemerli/RL-generator-2020-2021). 
There is also a test generator written by another supervisor, called Fabio Salice that I didn't used. You can find it [here](https://github.com/alessandrozito98/Progetto_Reti_Logiche_2020/tree/master/Public%20Tests/Testbench%20Generator).

-->
