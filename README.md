# Analyze Images using Amazon Rekognition

You can use this simple PoC tool (RIA) to quickly analyze a batch of images using Amazon Rekognition. You can run the tool by telling it where your images are in an S3 bucket. It then calls different Amazon Rekognition APIs (Labels, ModerationLabels, Faces, Celebrities, Text) for your images and generate a web app for you to visually see the results. As part of analysis it also generates a JSON and a CSV file that you can then use to further review the output.

## Output UI
![](assets/ria-html.png)

## CSV Export of Metadata
![](assets/ria-csv.png)


### Run RIA from Terminal/Command Prompt

1. Make sure you have following pre-requisites installed:
  - Python3
  - [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/installing.html)
  - [Pillow](https://pillow.readthedocs.io/en/5.3.x/#)
2. Download and unzip [ria.py.zip](./code/ria.py.zip)

3. Follow one the formats below to run batch image analysis (input-bucket is required, whereas all other parameters are optional). For detailed description of all arguments see below.
    - python3 ria.py --input-bucket your-bucket --input-directory your-input-directory --output-bucket your-bucket --output-directory your-output-directory

    - python3 ria.py --input-bucket your-bucket --input-directory your-input-directory --output-bucket your-bucket --output-directory your-output-directory --min-confidence 55 --s3-expiration-time 3600 --no-csv

### Run RIA from Jupyter

If you want to run RIA without installing and configuring AWS CLI, Python and other pre-requisites on your local machine then you can use a Jupyter instance. Follow steps below to create a Jupyter instance.

1. Click on one of the buttons below to launch CloudFormation template in an AWS region.

Region| Launch
------|-----
US East (N. Virginia) | [![Create SageMaker Instance](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/images/cloudformation-launch-stack-button.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?stackName=ria&templateURL=https://s3.amazonaws.com/aws-workshops-us-east-1/celebrity-rekognition/deployment/cf-sage-maker.yaml)
US East (Ohio) | [![Create SageMaker Instance](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/images/cloudformation-launch-stack-button.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-2#/stacks/create/review?stackName=ria&templateURL=https://s3.us-east-2.amazonaws.com/aws-workshops-us-east-2/celebrity-rekognition/deployment/cf-sage-maker.yaml)
US West (Oregon) | [![Create SageMaker Instance](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/images/cloudformation-launch-stack-button.png)](https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/create/review?stackName=ria&templateURL=https://s3-us-west-2.amazonaws.com/aws-workshops-us-west-2/celebrity-rekognition/deployment/cf-sage-maker.yaml)
EU (Ireland) | [![Create SageMaker Instance](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/images/cloudformation-launch-stack-button.png)](https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/create/review?stackName=ria&templateURL=https://s3-eu-west-1.amazonaws.com/aws-workshops-eu-west-1/celebrity-rekognition/deployment/cf-sage-maker.yaml)

2. Under Create stack, check the checkbox for "I acknowledge that AWS CloudFormation might create IAM resources with custom names" and click Create.

3. After CloudFormation template is complete, Click on the Output tab and click on the link for NotebookInstanceName.

4. From your SageMaker instance click on the Open Jupyter button.

5. Click on New and then Terminal. In the terminal type:
- cd SageMaker
- git clone https://github.com/darwaishx/ria

6. Go back to Jupyter home screen by clicking on the Jupyter logo on the top left and refresh to see the folder ria.

7. Click on ria, then code and then ria.ipynb to open the notebook.

8. Scroll to bottom of the Notebook and update runCommand:
    - runCommand = 'python3 ria.py --input-bucket INPUT-BUCKET --input-directory INPUT-DIRECTORY --output-bucket OUTPUT-BUCKET --output-directory OUTPUT-DIRECTORY'

## Arguments

  | Argument  | Description |
  | ------------- | ------------- |
  | --input-bucket  | Name of input S3 bucket with images  |
  | --input-directory  | Name of folder in S3 bucket with images |
  | --output-bucket  | Name of input S3 bucket where output will be saved |
  | --output-directory  | Name of folder in S3 bucket where output will be saved |
  | --min-confidence  | Confidence score |
  | --s3-expiration-time  | Expiration time for S3 Presigned URLs |
  | --collection-id  | Name of your collection id |
  | --no-csv  | Do not generate CSV file |
  | --no-api-labels  | Do not call Labels API |
  | --no-api-moderation-labels  | Do not call Moderation Labels API |
  | --no-api-celebrities  | Do not call Celebrities API |
  | --no-api-faces  | Do not call Faces API |
  | --no-api-text  | Do not call Text API |
