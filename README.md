The source code for the paper:


**Instructions for running the code in a cloud (GPU) system**:<br/>
First, make sure that you have installed on your computer:<br/>
-Python (3.9 – recommended)<br/>
-Microsoft Visual C++ (for Windows OS only)

Then, you have to install all the required packages, using the command:<br/>
`pip install -r requirements.txt`

This allows a user to avoid the hassle of individually installing each required library, as well as resolving potential compatibility issues (since the library versions in the requirements file have been tested and found to be fully functional). <br/>

We mainly recommend the use of cuda:<br/>
CUDA Toolkit 11.0

Since the approach hosts Ditto and GNEM matching tools, please find the respective projects:<br/>
https://github.com/megagonlabs/ditto<br/>
https://github.com/ChenRunjin/GNEM<br/>


Now you can run the local version using the command:<br/>
CUDA_VISIBLE_DEVICES=0 python SAFER_run_gpu.py <dataset_path> <top-k_value> <dataset_name> <ML_matcher_value> <similarity_threshold> <number_entities> <tau> <ranking_method> <matching_tool><br/>
CUDA_VISIBLE_DEVICES=0 python SAFER_run_gpu.py data/er_magellan/Structured/ 20 Amazon-Google roberta 0.1 199 30 m-fair gnem<br/>

The datasets are available at data/er_magellan/Structured.<br/> 

Finally, it is also recommended to use a VM with more than 6GB of RAM + NVIDIA T4, otherwise the system may be unstable.<br/>

In case of problems or questions, please report an issue, or contact Tiago Araújo (tiago.brasileiro AT ifpb DOT edu DOT br).
