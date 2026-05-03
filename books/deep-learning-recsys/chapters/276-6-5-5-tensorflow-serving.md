## 6.5.5 TensorFlow Serving

TensorFlow Serving is a native model server developed by TensorFlow. Essentially, the workflow of TensorFlow Serving is the same as that of PMML-like tools. The difference is that TensorFlow defines its own model serialization standard. Using the model serialization function that comes with TensorFlow, the trained model parameters and structures can be saved to a designated file.

The most common and convenient way to use TensorFlow Serving is to use Docker to build a model serving API. After the Docker environment is prepared, the installation and preparation of the TensorFlow Serving environment only needs to be done by pulling the image (pull image) using the following command:

```
docker pull tensorflow/serving
```

After starting the docker container, we can also start the model service API with only one line of command:

```
tensorflow_model_server --port=8500 --rest_api_port=8501 \ --model_name=${MODEL_NAME} --model_base_path=${MODEL_BASE_PATH}/${MODEL_NAME}
```

Here, we just need to change the model file path.

Of course, it is not easy to build a complete set of TensorFlow Serving services, because it involves a series of engineering issues such as model update, maintenance, and on-demand expansion of the entire docker container cluster. The performance of TensorFlow Serving is still criticized by the industry because of its limitations, but its ease of use and support for complex models make it the first choice for launching TensorFlow models.

