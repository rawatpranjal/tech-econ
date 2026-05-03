## 6.2.2 Parallel Training Mechanism in Spark MLlib

With the foundation of Spark's distributed computing process, you can more clearly understand the model parallel training mechanism in Spark MLlib.

The model structure can determine the degree of parallelism it has in the training process. For example, a Random Forest model can fully perform data-parallel model training, while the structural characteristics of GBDT determine that it can only be trained sequentially. In this section, we will focus on the implementation of gradient descent method, because the parallelism of gradient descent directly determines the training speed of deep learning models.

In  order  to  more  accurately  understand  the  specific  implementation  of  the Spark  parallel  gradient  descent  method,  we  will  dive  deep  into  the  source  code of Spark MLlib, and directly post the source code of Spark for minibatch gradient descent (the code is taken from the runMiniBatchSGD function of the Spark 2.4.3 GradientDescent class):

```
while (! converged && i <= numIterations) { val bcWeights = data.context.broadcast ( weights ) // Sample a subset (fraction miniBatchFraction) of the total data // compute and sum up the subgradients on this subset (this is one map-reduce) val ( gradientSum, lossSum, miniBatchSize ) = data.sample (false , miniBatchFraction, 42 + i ) .treeAggregate (( BDV.zeros [ Double ]( n ) , 0.0, 0L ))( seqOp = ( c, v ) => { // c: (grad, loss, count), v: (label, features) val l = gradient.compute ( v._2, v._1, bcWeights.value, Vectors.fromBreeze ( c._1 )) ( c._1, c._2 + l, c._3 + 1 ) } ,
```

combOp = ( c1, c2 ) =&gt; { // c: (grad, loss, count) ( c1.\_1 += c2.\_1, c1.\_2 + c2.\_2, c1.\_3 + c2.\_3 ) }) bcWeights.destroy ( blocking = false) if ( miniBatchSize &gt; 0 ) { /** * lossSum is computed using the weights from the previous iteration * and regVal is the regularization value computed in the previous iteration as well. */ stochasticLossHistory += lossSum / miniBatchSize + regVal val update = updater.compute ( weights, Vectors.fromBreeze ( gradientSum / miniBatchSize. toDouble ) , stepSize, i, regParam) weights = update.\_1 regVal = update.\_2 previousWeights = currentWeights currentWeights = Some ( weights ) if ( previousWeights ! = None &amp;&amp; currentWeights ! = None ) { converged = isConverged ( previousWeights.get, currentWeights.get, convergenceTol ) } } else { logWarning ( s'Iteration ($i/$numIterations). The size of sampled batch is zero' ) } i += 1 } This code looks complicated at first glance. But after we extract the key operations as shown next, the main process of Spark gradient descent calculation turns easy to understand. //broadcasting //compute the gradient in each sample,

```
while ( i <= numIterations ) { //limit the maximum iterations val bcWeights = data.context.broadcast ( weights ) all the weights val ( gradientSum, lossSum, miniBatchSize ) = data.sample (false , miniBatchFraction, 42 + i ) .treeAggregate () then get gradientSum using treeAggregate function val weights = updater.compute ( weights, gradientSum / miniBatchSize ) //update the weights based on gradients i += 1 //iteration + 1 }
```

This  simplified  code  is  quite  easy  to  understand.  Basically,  Spark's  minibatch process has three steps:

- (1)  Broadcast the current model parameters to each data partition (which can be used as a virtual computing node).
- (2)  Each  computing node performs data sampling to obtain minibatch data, calculates the gradients separately, and then aggregates the gradients through the treeAggregate operation to obtain the final gradientSum.
- (3)  Use gradientSum to update model weights.

In this way, the boundaries of stages in each iteration are very clear. The parallel part inside each stage is the process of sampling and calculating the gradient of each node separately, and the boundary of stage is the process of summarizing and summing the gradient of each node. Here we will highlight the operation treeAggregate, which aggregates the gradients from all the nodes. This operation is a layer-by-layer aggregation based on a tree-like structure. The whole process is a reduce operation and does not include a shuffle operation. In addition, a hierarchical tree operation is used. Tree node operations are performed in parallel, so the whole process is very efficient.

After the number of iterations reaches the upper limit or the model has sufficiently converged, the model stops training. This is the whole process of minibatch gradient descent calculation in Spark MLlib, and it is also the most representative implementation of distributed model training in Spark MLlib.

In  summary,  Spark  MLlib's  parallel  training  process  is  actually  through  data parallelism, which does not involve a complex gradient update strategy, and does not implement parallel training  through  parameter  parallelism.  This  method  is  simple, intuitive, and easy to implement, but there are also some limitations.

