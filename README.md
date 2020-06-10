# DP_Health_AWS
DefencePro Health testing for AWS.

## Table Of Contents ###
- [Description](#description )
- [Detector Lambda](#detector-lambda)
  * [Permissions](#detector-lambda-permissions)
- [Metric Filter](#metric-filter)
- [Alarm](#alarm)
- [CloudWatch Rules](#cloudwatch-rules)
- [Action Lambda](#action-lambda)
  * [Permissions](#action-lambda-permissions)

## Description ##
This repository holds the Lambda functions as well as their requirements for performing automatic bypass of DefencePro in AWS environment.
Before we begin, this solution assumes the following:
* All relevant objects are in the same VPC
* Protected objects (servers) are in a subnet which routing table points to the ENI of DefencePro - we will refer this routing table as `Reals`
* There is a routing table with the Internet Gateway assigned as the `Edge Gateway` with a route sending the Protected objects\their entire subnet to ENI of DefencePro - we will refer this routing table as `GatewayID`
* All Relevant route tables has a tag named `DefenceProTable`, the value represents the table type (F.E: for protected objects route table it would be `Reals`)

## Detector Lambda ##
The code, as well as the requirements are in `Detect` folder. This Lambda is responsible for:
1. Discovering the DefensePro devices based on a TAG `DefenceProInstance`
2. Quarrying the DefensePro devices with an SNMP request to the MGMT interface
3. Issue an HTTP\S query through the DefencePro 
4. Write test results to a CloudWatch Log Group.

For achieving the above - this Lambda is in the same VPC as the DefencePro and the protected objects.

### Detector Lambda Permissions ###
In order to oporate the Lambda needs the following permissions:
```
        "Action": [
            "ec2:CreateNetworkInterface",
            "ec2:DescribeInstances",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DescribeTags",
            "ec2:DeleteNetworkInterface"
        ], "Resource": "*"
    }, {
        "Action": [
            "logs:CreateLogStream",
            "logs:PutLogEvents"
        ], "Resource": "arn:aws:logs:us-east-2:334049999223:log-group:/aws/lambda/dp_ha_detect_v2:*"
    }, 
    { "Action": "logs:CreateLogGroup", "Resource": "arn:aws:logs:us-east-2:334049999223:*" } 
```

## Metric Filter ##
The results of the Detector Lambda are sent to Log group, to read them - we will use Metric Filter. <br>
a Metric Filter is representing only one value for one DefencePro (F.E. the SNMP result for "DP1") .<br>
We use the Filter Pattern to narrow down the relevant logs in the following manner <br>
`{ ($.Name = DP1) && $.SNMP_Result>=0 }`<br>
this means we only want logs where the Name is "DP1" and `SNMP_Result` is greater or equal to 0. <br>
And we should use `$.SNMP_Result` for the Metric Value.<br>

## Alarm ##
To set thresholds on each metric we should use the CloudWatch Alarm and point it to a Metric (created by the Metric filter). <br>
We need to create a separate Alarm for each metric (it's recomended to set norification to all Alerts).<br>

## CloudWatch Rules ##
To schedule the Detector Lambda we are going to use a schedule rule triggering the Lambda once every 10 Minutes.<br>
For performing the acctual failover, we are going to use an additional Rule triggering Action Lambda on <b>any<b> alarm change.<br>

## Action Lambda ## 
this Lambda is responsible for:
1. discovering all relevant route tables (based on tags)
2. replace association between Public and Protected object route table (for passing or bypassing the DefencePro)
3. removal or association of the internet gateway from the `GatewayID` route table (for passing or bypassing the DefencePro)

### Action Lambda Permissions ###
In order to oporate the Lambda needs the following permissions:
```
    "Effect": "Allow",
    "Action": [
        "ec2:DescribeInternetGateways",
        "logs:CreateLogStream",
        "ec2:DeleteTags",
        "ec2:DescribeTags",
        "ec2:CreateTags",
        "ec2:DisassociateRouteTable",
        "logs:CreateLogGroup",
        "logs:PutLogEvents",
        "ec2:DescribeRouteTables",
        "ec2:AssociateRouteTable"
    ],
    "Resource": "*"
```
