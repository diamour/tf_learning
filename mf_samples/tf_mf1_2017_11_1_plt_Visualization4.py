##About the basic training of the data, y=ax+b

import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt

def add_layer(inputs,in_size,out_size,activation_function=None):
    #Matrix
    Weights=tf.Variable(tf.random_normal([in_size,out_size]))
    #vector
    biases=tf.Variable(tf.zeros([1,out_size])+0.1)
    Wx_plus_b=tf.matmul(inputs,Weights)+biases
    if activation_function is None:
        outputs=Wx_plus_b
    else:
        outputs=activation_function(Wx_plus_b)
    return outputs

x_data=np.linspace(-1,1,300)[:,np.newaxis]
noise=np.random.normal(0,0.05,x_data.shape)
y_data=np.square(1-x_data*x_data)+noise


xs=tf.placeholder(tf.float32,[None,1])
ys=tf.placeholder(tf.float32,[None,1])

l1=add_layer(xs,1,10,activation_function=tf.nn.relu)
l2=add_layer(l1,10,20,activation_function=tf.nn.relu)
l3=add_layer(l2,20,10,activation_function=tf.nn.relu)
prediction=add_layer(l3,10,1,activation_function=None)

loss=tf.reduce_mean(tf.reduce_sum(tf.square(ys-prediction),
                                  reduction_indices=[1]))
train_step=tf.train.AdamOptimizer(0.01).minimize(loss)

#initialize the Variable
init=tf.global_variables_initializer()

sess=tf.Session()
sess.run(init)

#create plt
fig=plt.figure()
ax=fig.add_subplot(1,1,1)
ax.scatter(x_data,y_data)
#make the plt show not chock
plt.ion()
plt.show()

for i in range(1000):
    sess.run(train_step,feed_dict={xs:x_data,ys:y_data})
    if i%10==1:
        print(sess.run(loss,feed_dict={xs:x_data,ys:y_data}))
        prediction_value=sess.run(prediction,feed_dict={xs:x_data})
        try:
            #remove old and can create new
            ax.lines.remove(lines[0])
        except Exception:
            pass
        #red line,width=5
        lines=ax.plot(x_data,prediction_value,'r-',lw=1)
        plt.pause(0.01)