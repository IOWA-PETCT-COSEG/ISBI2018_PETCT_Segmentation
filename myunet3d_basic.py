import tensorflow as tf
import numpy as np

def get_kernel_size(factor):
    """
    Find the kernel size given the desired factor of upsampling.
    """
    return 2 * factor - factor % 2

def myunet3d_crf(name,
           inputs, 
           num_classes,
           phase_train,
           use_bias=False,
           kernel_initializer=tf.initializers.variance_scaling(distribution='uniform'),
           bias_initializer=tf.zeros_initializer(),
           kernel_regularizer=None,
           bias_regularizer=None,
           use_crf=False,
           args=None):
    
    conv_params = {'padding': 'same',
                   'use_bias': use_bias,
                   'kernel_initializer': kernel_initializer,
                   'bias_initializer': bias_initializer,
                   'kernel_regularizer': kernel_regularizer,
                   'bias_regularizer': bias_regularizer}
    deconv_params = {'padding': 'same',
                     'use_bias': False,
                     'kernel_initializer': kernel_initializer,
                     'bias_initializer': bias_initializer,
                     'kernel_regularizer': kernel_regularizer,
                     'bias_regularizer': bias_regularizer}
    x = inputs
    
    with tf.variable_scope(name):
        with tf.variable_scope('enc_0'):
            x = tf.layers.conv3d(x, 32, 3, **conv_params)
        f1 = x
        print(f1.shape)
        
        with tf.variable_scope('enc_1'):
            x = tf.layers.conv3d(x, 64, 3, **conv_params)
            x = tf.nn.relu(x) 
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f2 = x # 32x64x64x32
        print(f2.shape)
    
        with tf.variable_scope('enc_2'):
            x = tf.layers.conv3d(x, 128, 3, **conv_params)
            x = tf.nn.relu(x) 
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f3 = x # 16x32x32x64
        print(f3.shape)
    
        with tf.variable_scope('enc_3'):
            x = tf.layers.conv3d(x, 256, 3, **conv_params)
            x = tf.nn.relu(x) 
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f4 = x # 8x16x16x128
        print(f4.shape)
    
        with tf.variable_scope('enc_4'):
            x = tf.layers.conv3d(x, 512, 3, **conv_params)
            x = tf.nn.relu(x)
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f5 = x # 4x8x8x256
        print(f5.shape)
        
        with tf.variable_scope('dec_4'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 512, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x, f4], axis=4) # 8x16x16x256
            x = tf.layers.conv3d(x, 256, 3, **conv_params)
            x = tf.nn.relu(x)
        print(x.shape)
            
        with tf.variable_scope('dec_3'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 256, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x,f3], axis=4) # 16x32x32x256
            x = tf.layers.conv3d(x, 128, 3, **conv_params)
            x = tf.nn.relu(x)
        print(x.shape)
        
        with tf.variable_scope('dec_2'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 128, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x,f2], axis=4)
            x = tf.layers.conv3d(x, 64, 3, **conv_params)
            x = tf.nn.relu(x)
        print(x.shape)
        
        with tf.variable_scope('dec_1'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 64, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x,f1], axis=4)
            x = tf.layers.conv3d(x, 32, 3, **conv_params)
            x = tf.nn.relu(x)
        print(x.shape)
            
        with tf.variable_scope('conv_cls'):
            x = tf.layers.conv3d(x, num_classes, 1, padding='same',
                                 use_bias=True,
                                 kernel_initializer=tf.truncated_normal_initializer(stddev=0.1),
                                 bias_initializer=tf.constant_initializer(value=0.1),
                                 kernel_regularizer=tf.contrib.layers.l2_regularizer(4e-4),
                                 bias_regularizer=tf.contrib.layers.l2_regularizer(4e-4))
        print(x.shape)
        
        logits = x
        
        if use_crf:
            logits_crf  = crfrnn3d(name='crf',
                          unary=logits,
                          feats=inputs,
                          sw_weight=args.sw_weight,
                          bw_weight=args.bw_weight,
                          cm_weight=args.cm_weight,
                          theta_alpha=args.theta_alpha,
                          theta_beta=args.theta_beta,
                          theta_gamma=args.theta_gamma,
                          num_iterations=args.num_iterations)
     
        outputs = {}
        # Define the outputs
        outputs['logits'] = logits
     
        with tf.variable_scope('pred'):
            y_prob = tf.nn.softmax(logits)
            outputs['y_prob'] = y_prob
     
            y_ = tf.argmax(logits, axis=-1) \
                if num_classes > 1 \
                else tf.cast(tf.greater_equal(logits[..., 0], 0.5), tf.int32)
     
            outputs['y_'] = y_
         
         
        if use_crf:
            outputs['logits_crf'] = logits_crf
            with tf.variable_scope('pred_crf'):
                y_prob_crf = tf.nn.softmax(logits_crf)
                outputs['y_prob_crf'] = y_prob_crf
         
                y_crf = tf.argmax(logits_crf, axis=-1) \
                    if num_classes > 1 \
                    else tf.cast(tf.greater_equal(logits_crf[..., 0], 0.5), tf.int32)
         
                outputs['y_crf'] = y_crf
 
    return outputs

def myunet3d_bn_crf(name,
           inputs, 
           num_classes,
           phase_train,
           use_bias=False,
           kernel_initializer=tf.initializers.variance_scaling(distribution='uniform'),
           bias_initializer=tf.zeros_initializer(),
           kernel_regularizer=None,
           bias_regularizer=None,
           use_crf=False,
           args=None):
    
    conv_params = {'padding': 'same',
                   'use_bias': use_bias,
                   'kernel_initializer': kernel_initializer,
                   'bias_initializer': bias_initializer,
                   'kernel_regularizer': kernel_regularizer,
                   'bias_regularizer': bias_regularizer}
    deconv_params = {'padding': 'same',
                     'use_bias': False,
                     'kernel_initializer': kernel_initializer,
                     'bias_initializer': bias_initializer,
                     'kernel_regularizer': kernel_regularizer,
                     'bias_regularizer': bias_regularizer}
    x = inputs
    
    with tf.variable_scope(name):
        with tf.variable_scope('enc_0'):
            x = tf.layers.conv3d(x, 32, 3, **conv_params)
        f1 = x
        print(f1.shape)
        
        with tf.variable_scope('enc_1'):
            x = tf.layers.conv3d(x, 64, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x) 
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f2 = x # 32x64x64x32
        print(f2.shape)
    
        with tf.variable_scope('enc_2'):
            x = tf.layers.conv3d(x, 128, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x) 
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f3 = x # 16x32x32x64
        print(f3.shape)
    
        with tf.variable_scope('enc_3'):
            x = tf.layers.conv3d(x, 256, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x) 
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f4 = x # 8x16x16x128
        print(f4.shape)
    
        with tf.variable_scope('enc_4'):
            x = tf.layers.conv3d(x, 512, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x)
            x = tf.layers.max_pooling3d(x, pool_size=[2,2,2], strides=[2,2,2], padding='same')
        f5 = x # 4x8x8x256
        print(f5.shape)
        
        with tf.variable_scope('dec_4'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 512, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x, f4], axis=4) # 8x16x16x256
            x = tf.layers.conv3d(x, 256, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x)
        print(x.shape)
            
        with tf.variable_scope('dec_3'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 256, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x,f3], axis=4) # 16x32x32x256
            x = tf.layers.conv3d(x, 128, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x)
        print(x.shape)
        
        with tf.variable_scope('dec_2'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 128, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x,f2], axis=4)
            x = tf.layers.conv3d(x, 64, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x)
        print(x.shape)
        
        with tf.variable_scope('dec_1'):
            factor = 2
            x = tf.layers.conv3d_transpose(x, 64, kernel_size=get_kernel_size(factor), 
                                           strides=[factor, factor, factor], 
                                           **deconv_params)
            x = tf.concat([x,f1], axis=4)
            x = tf.layers.conv3d(x, 32, 3, **conv_params)
            x = tf.layers.batch_normalization(
                x, training=phase_train)
            x = tf.nn.relu(x)
        print(x.shape)
            
        with tf.variable_scope('conv_cls'):
            x = tf.layers.conv3d(x, num_classes, 1, padding='same',
                                 use_bias=True,
                                 kernel_initializer=tf.truncated_normal_initializer(stddev=0.1),
                                 bias_initializer=tf.constant_initializer(value=0.1),
                                 kernel_regularizer=tf.contrib.layers.l2_regularizer(4e-4),
                                 bias_regularizer=tf.contrib.layers.l2_regularizer(4e-4))
        print(x.shape)
        
        logits = x
        
        if use_crf:
            logits_crf  = crfrnn3d(name='crf',
                          unary=logits,
                          feats=inputs,
                          sw_weight=args.sw_weight,
                          bw_weight=args.bw_weight,
                          cm_weight=args.cm_weight,
                          theta_alpha=args.theta_alpha,
                          theta_beta=args.theta_beta,
                          theta_gamma=args.theta_gamma,
                          num_iterations=args.num_iterations)
    
        outputs = {}
        # Define the outputs
        outputs['logits'] = logits
    
        with tf.variable_scope('pred'):
            y_prob = tf.nn.softmax(logits)
            outputs['y_prob'] = y_prob
    
            y_ = tf.argmax(logits, axis=-1) \
                if num_classes > 1 \
                else tf.cast(tf.greater_equal(logits[..., 0], 0.5), tf.int32)
    
            outputs['y_'] = y_
        
        
        if use_crf:
            outputs['logits_crf'] = logits_crf
            with tf.variable_scope('pred_crf'):
                y_prob_crf = tf.nn.softmax(logits_crf)
                outputs['y_prob_crf'] = y_prob_crf
        
                y_crf = tf.argmax(logits_crf, axis=-1) \
                    if num_classes > 1 \
                    else tf.cast(tf.greater_equal(logits_crf[..., 0], 0.5), tf.int32)
        
                outputs['y_crf'] = y_crf

    return outputs


