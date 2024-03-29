import sp_utils as utils
from sp_utils.config import config
import logging
import os
import torch
from torch import nn
import torchvision as tv
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import cv2
from scipy import interpolate
import pandas as pd


def run_test_without_labels(model,testdata,device, logger,conf):
    model.eval()
    probability = np.zeros(0)
    X = np.zeros(0)
    Y = np.zeros(0)
    with torch.no_grad():
        for data in testdata:
            # logger.info("data file is {}".format(data))

            input_data = Image.open(data)
            input_data= input_data.convert("RGB")
            # logger.info("size of the input image {}".format(input_data.size))
            input_data= utils.trans_norm(input_data, conf.TEST.input_im_size)

            tensor_image = input_data.unsqueeze_(0)
            # logger.info("tensor of the input image {}".format(tensor_image.shape))

            inputs= tensor_image.to(device)
            logps = model.forward(inputs)


            prob_tensor = logps
            p_map = np.squeeze(prob_tensor.to("cpu").numpy())
            # logger.info("probability of spinous in frame {}".format(np.amax(p_map)))

            #### Final point prediction
            pred, _ = utils.get_max_preds(logps.detach().cpu().numpy())
            # prediction of the final point in dimentions of heatmap. Transfer it to image size
            pred = pred * config.TEST.input_im_size / config.TEST.heatmap_size
            probability = np.append(probability, np.amax(p_map))
            X = np.append(X, pred[0][0][0])
            Y = np.append(Y, config.TEST.input_im_size-pred[0][0][1])
            # logger.info("coordinates X {}, Y{}".format(pred[0][0][0],config.TEST.input_im_size-pred[0][0][1]))

            if conf.TEST.PLOT:
                p_map = np.multiply(p_map, 255)
                p_map_image = tv.transforms.ToPILImage()(p_map)
                p_map = tv.transforms.Resize((conf.TEST.input_im_size, conf.TEST.input_im_size))(p_map_image)

                inputs = utils.img_denorm(input_data)
                inputs = tv.transforms.ToPILImage()(inputs)




                plt.subplot(1, 2, 1)
                plt.imshow(inputs)
                plt.subplot(1, 2, 2)
                plt.imshow(p_map)
                plt.scatter(x=pred[0][0][0], y=pred[0][0][1], c='r', s=40)

                xs = X
                ys = Y
                zs = probability
                fig = plt.figure()
                ax = fig.add_subplot(111, projection='3d')
                ax.scatter(xs, ys, zs, c = "#1f77b4",marker="o")

                ax.set_xlabel('X Label')
                ax.set_ylabel('Y Label')
                ax.set_zlabel('Z Label')


                plt.show()

        if config.TRAIN.SWEEP_TRJ_PLOT:
            plot_path(probability,X,Y,"b")

def plot_path(probability, X, Y,color_ext,labels = None) :

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set(xlim=(0, 224), ylim=(0, len(probability)))

    path = np.zeros(0)
    index = np.zeros(0)
    zs = 0
    for i in range(0, len(X)):
        xs = X[i]
        ys = Y[i]

        if probability[i] > 0.7 and X[i] != 0:  # Spinous
            color = color_ext
            marker = "o"
            path= np.append(path,xs)
            index = np.append(index,i)
        else:  # Gap
            color = "#8c564b"
            marker = "x"

        ax.scatter(xs, zs, c=color, marker=marker)

        zs = zs + 1
    ax.plot(path, index, label="coordinate continious")
    t = np.linspace(0, zs, zs)


    # ax1.plot(probability,t_p)
    ax.set_xlabel(' X coordinate')
    ax.set_ylabel(' step')

    Dplot = False
    if Dplot:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')


        i = 0
        zs = 0

        for i in range(0,len(X)):
            xs = X[i]
            ys = Y[i]
            zs = zs+1
            if probability[i]>0.7: #Spinous
                color = "#1f77b4"
                marker = "o"
                ax.scatter(xs, zs, ys, c=color, marker=marker)
            else: #Gap
                color = "#1f77b4"
                marker = "x"



        t = np.linspace(0, zs*10, zs)
        ax.plot(X, t ,Y, label = "coordinate continious")
        ax.legend()
            # i =+1

        ax.set_xlabel('X Label - X coordinate')
        ax.set_ylabel('Y Label - step')
        ax.set_zlabel('Z Label - Y coordinate')
        plt.show()


def smoothed_trajectory(X_label_from_file, Y_label_from_file,datatype,*argv):
    '''datatype - "pred" or "label"'''
    X_label_from_file_with_NaN = np.zeros(0)
    Y_label_from_file_with_NaN = np.zeros(0)
    for arg in argv:
        probability = arg
    '''Replace 0 elements (which indicates label absence) to NaN, the same element for X and Y, because if label doesn't exist x,y equal to 0'''

    for i in range(np.size(X_label_from_file)):
        if datatype == "pred":
            if probability[i] < 0.71:
                X_label_from_file_with_NaN = np.append(X_label_from_file_with_NaN, np.nan)
                Y_label_from_file_with_NaN = np.append(Y_label_from_file_with_NaN, np.nan)
            else:
                X_label_from_file_with_NaN = np.append(X_label_from_file_with_NaN, X_label_from_file[i])
                Y_label_from_file_with_NaN = np.append(Y_label_from_file_with_NaN, Y_label_from_file[i])
        else:
            if X_label_from_file[i] == 0:
                X_label_from_file_with_NaN = np.append(X_label_from_file_with_NaN, np.nan)
                Y_label_from_file_with_NaN = np.append(Y_label_from_file_with_NaN, np.nan)
            else:
                X_label_from_file_with_NaN = np.append(X_label_from_file_with_NaN, X_label_from_file[i])
                Y_label_from_file_with_NaN = np.append(Y_label_from_file_with_NaN, Y_label_from_file[i])

    if np.isnan(X_label_from_file_with_NaN[0]):
        X_label_from_file_with_NaN[0] = 112  # middle of the frame

    if np.isnan(Y_label_from_file_with_NaN[0]):
        Y_label_from_file_with_NaN[0] = 0  # middle of the frame
    '''
    # interpolate the NaN to trajectory a size of the sweep

    '''
    X_label_interpolated = pd.DataFrame(X_label_from_file_with_NaN).interpolate().values.ravel().tolist()
    Y_label_interpolated = pd.DataFrame(Y_label_from_file_with_NaN).interpolate().values.ravel().tolist()
    X_Y_label_interpolated = np.column_stack((X_label_interpolated, Y_label_interpolated))
    X_label_interpolated_smoothed = utils.smooth(X_label_interpolated)
    # Y_label_interpolated_smoothed = utils.smooth(Y_label_interpolated)
    X_Y_label_interpolated_smoothed = np.column_stack((X_label_interpolated_smoothed, Y_label_interpolated))
    return X_label_interpolated_smoothed, X_Y_label_interpolated_smoothed

def run_val(model, valloader, device, criterion,logger,config,patient):
    '''
        Main function to run if the sweep is labeled and labels exist in the folder
        This function can record video of the sweep with the detected point and label on it
        It can also generate the plot of trajectories and save to npz file
    '''
    val_loss = 0
    acc = utils.AverageMeter()
    dist_error = utils.AverageMeter()
    dist_error_calculated = utils.AverageMeter()
    model.eval()
    probability = np.zeros(0)
    probability_label = np.zeros(0)
    X = np.zeros(0)
    Y = np.zeros(0)
    X_label = np.zeros(0)
    Y_label = np.zeros(0)

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    '''if the size of the frames doesn't match with the size in "out", the video will not play'''
    # out = cv2.VideoWriter('output_original_%s.avi'%(patient), fourcc, 2.0, (448, 224)) # for two images of size 244*244
    out = cv2.VideoWriter(config.TEST.save_dir+'output_original_%s.avi' % (patient), fourcc, 3.0, (1280, 480))# for two images of size 480*640

    if config.TEST.PLOT_SMOOTH_LABEL_TRAJECTORY == True:
        '''#Load pre-recorded trajectory (based on labels) from npz file - probability=probability, X=X, Y=Y, X_label=X_label, Y_label=Y_label'''
        data_sweep_recorded = np.load("/media/maryviktory/My Passport/spine navigation Polyu 2021/DATASET_polyu/FCN_PWH_train_dataset_heatmaps/output/%s.npz"%(patient))
        X_label_from_file = data_sweep_recorded["X_label"]
        Y_label_from_file = data_sweep_recorded["Y_label"]
        X_pred_from_file = data_sweep_recorded["X"]
        Y_pred_from_file = data_sweep_recorded["Y"]
        probability_from_file = data_sweep_recorded["probability"]
        num_sweep_frames = np.size(X_label_from_file)
        print(num_sweep_frames)

        X_label_interpolated_smoothed, X_Y_label_interpolated_smoothed = smoothed_trajectory(X_label_from_file, Y_label_from_file,datatype = "label")

        X_pred_interpolated_smoothed, X_Y_pred_interpolated_smoothed = smoothed_trajectory(X_pred_from_file,
                                                                                             Y_pred_from_file,"pred",probability_from_file)


        # print(X_label_interpolated)
        # print(X_label_from_file_with_NaN)
        # print(X_label_from_file[0])
        # print(np.isnan(X_label_from_file[0]))

        # print(X_label_from_file_with_NaN)



    with torch.no_grad():
        for i, (inputs, labels) in enumerate(valloader):
            print("frame num {}",i)


            inputs, labels = inputs.to(device), labels.to(device)

            logps = model.forward(inputs)

            batch_loss = criterion(logps, labels.float())
            val_loss += batch_loss.item()

            acc_functional, avg_acc, cnt, pred,target, dists = utils.accuracy(logps.detach().cpu().numpy(),
                                             labels.detach().cpu().numpy(),thr = config.TRAIN.THRESHOLD)

            acc.update(avg_acc, cnt)
            logger.info("Accuracy batch {}".format(avg_acc))
            logger.info("Accuracy functional batch {}".format(acc_functional))
            p_map = np.squeeze(logps.to("cpu").numpy())
            probab_frame = np.amax(p_map)
            logger.info("prediction max: {}".format(np.amax(p_map)))

##############__DIstance calculation ######
            real_distance = utils.real_distance_error_calculation(dists, config)
            if dists != -1:
                dist_error.update(real_distance)
            logger.info("distance from accuracy function {}, "
                        ", real distance {}mm".format(dists, real_distance))


###############__PATH_RECONSTRUCTION__
            pred = pred * config.TEST.input_im_size / config.TEST.heatmap_size
            probability = np.append(probability, np.amax(p_map))
            X = np.append(X, pred[0][0][0])
            Y = np.append(Y, config.TEST.input_im_size - pred[0][0][1])

            label_np = labels.detach().cpu().numpy()
            if np.sum(label_np) == 0:
                probability_label = np.append(probability_label, 0)
            else:
                probability_label = np.append(probability_label, 1)

            # convert target position from 56*56 size to 224*224
            target = target * config.TEST.input_im_size / config.TEST.heatmap_size
            X_label = np.append(X_label, target[0][0][0])
            Y_label = np.append(Y_label, target[0][0][1])

            #Y_label = np.append(Y_label, config.TEST.input_im_size - target[0][0][1])
            if config.TEST.SAVE_NPZ_FILE == True:
                # save target position to csv file for the following trajectory smoothing and ploting.
                # The coordinates in the image size of 224*224
                np.savez(os.path.join(config.TEST.save_dir, patient + '.npz'), probability=probability, X=X, Y=Y, X_label=X_label, Y_label=Y_label)

            # print(probability_label,X_label,Y_label)
            ################___ _Transformations for plotting ####################
            if config.TEST.PLOT:

                inputs = utils.img_denorm(inputs)
                inputs = tv.transforms.ToPILImage()(inputs)
                input_img = inputs

                print(inputs.size)

                p_map = np.multiply(p_map,255)
                p_map_im = p_map
                p_map_image = tv.transforms.ToPILImage()(p_map)
                p_map_image = p_map_image.convert("RGB")
                p_map_resized = tv.transforms.Resize((224, 224))(p_map_image)

                transformed_label = np.squeeze(labels)
                transformed_label = tv.transforms.ToPILImage()(transformed_label)
                transformed_label = transformed_label.convert("RGB")
                labels_im = tv.transforms.Resize((224, 224))(transformed_label)

                # resized_label = tv.transforms.Resize((224, 224))(transformed_label)

                # row,column = np.where(p_map > np.amax(p_map)/10)
                plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=0.2, hspace=0.3)

                plt.subplot(3, 3, 4)
                plt.imshow(input_img)
                plt.title('input image',y=1.02,fontsize=10)

                plt.subplot(3, 3, 2)
                plt.imshow(p_map_resized)
                plt.title('probability map resized', y=1.02, fontsize=10)

                plt.subplot(3, 3, 1)
                plt.imshow(labels_im)
                plt.title('label', y=1.02, fontsize=10)

                plt.subplot(3, 3, 3)
                plt.imshow(p_map_im)
                plt.title('Probability map', y=1.02, fontsize=10)

                plt.subplot(3, 3, 5)
                plt.imshow(input_img)
                plt.title('input image + predicted point', y=1.02, fontsize=10)

                # put a red dot, size 40, at 2 locations:
                print(probab_frame)
                if probab_frame>0.5:
                    plt.scatter(x=pred[0][0][0], y=pred[0][0][1], c='r', s=40)

                # plt.subplot(3, 3, 5)
                # plt.imshow(input_img)
                # plt.scatter(x=column*4, y=row*4, c='b', s=10) #4 is a koefficient, 224/56 - image size/heatmap size
                # plt.title('input image + "projected heatmap" ', y=1.02, fontsize=8)
                plt.show()

            if config.TEST.VIDEO:

                if config.TEST.enable_transform == True:
                    inputs = utils.img_denorm(inputs)
                    inputs = tv.transforms.ToPILImage()(inputs)
                else:
                    inputs = utils.img_denorm(inputs)
                    inputs = np.squeeze(inputs)
                    inputs = tv.transforms.ToPILImage()(inputs)

                inputs = np.array(inputs)

                inputs_copy = inputs.copy()
                transformed_label = np.squeeze(labels)
                transformed_label = tv.transforms.ToPILImage()(transformed_label)
                # transformed_label = transformed_label.convert("LA")
                label_im = tv.transforms.Resize((224, 224))(transformed_label)

                label_im_cv = cv2.cvtColor(np.array(label_im) , cv2.COLOR_RGB2BGR) #cv2.COLOR_RGB2BGR, cv2.COLOR_BGR2GRAY
                # Set threshold level
                label_im_cv_gray =  cv2.cvtColor(label_im_cv, cv2.COLOR_BGR2GRAY)
                # print("gray image",label_im_cv_gray.shape)

                # Find coordinates of all pixels below threshold
                threshold_level = 127 #half of 255
                coords = np.column_stack(np.where(label_im_cv_gray > threshold_level))
                # print(label_im_cv_gray[coords[0][0],coords[0][1]])
                # print(coords[0])
                image_predicted = inputs


                for pose in coords:
                    # print(pose)
                    color_intensity = label_im_cv_gray[pose[0],pose[1]]
                    # print(color_intensity)
                    cv2.circle(image_predicted, (pose[1],pose[0]), 0, (int(color_intensity), 0, 0), -1)
                # print("max pixel intensity",np.amax(label_im))

                # PUT TEXT ON IMAGE - probabilities
                color = (0, 255, 0);
                thickness = 1;
                font = cv2.FONT_HERSHEY_SIMPLEX;
                org = (20, 200);
                fontScale = 0.5
                image_predicted = cv2.putText(image_predicted, 'probability %s' % (round(probab_frame,2)), org, font,
                                              fontScale, color, thickness, cv2.LINE_AA)
                #Only if the probability is larger than 0.7 it is counted as detected
                if probab_frame>0.7:
                    x, y = pred[0][0][0], pred[0][0][1]
                    # x = int((pred[0][0][0]) * 640 / 244)
                    # y = int((pred[0][0][1]) * 480 / 244)
                    x_scaled,y_scaled = int(x*(config.TEST.ORIGINAL_IMAGE_SIZE/config.TEST.input_im_size)),int(y*((config.TEST.ORIGINAL_IMAGE_HEIGHT/config.TEST.input_im_size)))
                    print("predicted coordinate in dimentions 244*244",x, y)
                    print("target coordinate in dimentions 244*244", target[0][0][0], target[0][0][1])
                    print("predicted coordinate in dimentions 480*640", x_scaled, y_scaled )
                    image_predicted = cv2.circle(inputs, (x, y), radius=1, color=(0, 0, 255), thickness=-1)
                    #distance calculated only for detected points
                    distance = np.abs(int(round(X_Y_label_interpolated_smoothed[i][0])) -int(round(X_Y_pred_interpolated_smoothed[i][0])))
                    print(X_Y_label_interpolated_smoothed[i][0])
                    print(X_Y_label_interpolated_smoothed)
                    print(X_Y_pred_interpolated_smoothed)
                    print(X_Y_pred_interpolated_smoothed[i][0])
                    print('Smoothed trajectory distance pixels in 224*224',distance)
                    print('Smoothed trajectory distance pixels in 480*640 {}, {} mm'.format( (640*distance/224),(640*distance/224)/8) ) # 8 - 640/80mm
                    dist_error_calculated.update(640*distance/224)
                    # PUT smoothed Target trajectory on to the video from pre-recorded file
                if config.TEST.PLOT_SMOOTH_LABEL_TRAJECTORY == True:
                    # cv2.circle(image_predicted, (int(round(X_Y_label_interpolated_smoothed[i][0])),
                    #                              int(round(X_Y_label_interpolated_smoothed[i][1]))), 2, (0, 255, 0),-1)
                    cv2.line(image_predicted,(int(round(X_Y_label_interpolated_smoothed[i][0])),0),(int(round(X_Y_label_interpolated_smoothed[i][0])),480),(0, 255, 0))
                    cv2.line(image_predicted, (int(round(X_Y_pred_interpolated_smoothed[i][0])), 0),
                             (int(round(X_Y_pred_interpolated_smoothed[i][0])), 480), (0,0 , 255))

                image_predicted = tv.transforms.ToPILImage()(image_predicted)
                inputs_copy = tv.transforms.ToPILImage()(inputs_copy)

                image_predicted = tv.transforms.Resize((config.TEST.ORIGINAL_IMAGE_HEIGHT, config.TEST.ORIGINAL_IMAGE_SIZE))(image_predicted)
                inputs_copy = tv.transforms.Resize((config.TEST.ORIGINAL_IMAGE_HEIGHT, config.TEST.ORIGINAL_IMAGE_SIZE))(inputs_copy)

                # cv2.imshow("Result", np.hstack([inputs_copy, image_predicted]))

                out.write(np.hstack([inputs_copy, image_predicted]))
                if config.TEST.PLOT_VIDEO:
                    inputs_copy = cv2.cvtColor(np.array(inputs_copy), cv2.COLOR_BGR2RGB)
                    image_predicted = cv2.cvtColor(np.array(image_predicted), cv2.COLOR_BGR2RGB)


                    plt.subplot(1, 2, 1)
                    plt.imshow(inputs_copy)
                    plt.title('input', y=1.02, fontsize=10)

                    plt.subplot(1, 2, 2)
                    plt.imshow(image_predicted)
                    plt.title('Predicted + label', y=1.02, fontsize=10)

                    plt.show()
                # cv2.waitKey(1)
                #distance calculation:
                # np.abs(X_Y_label_interpolated_smoothed[i][0]-

        logger.info("Accuracy mean {}".format(acc.avg))
        logger.info("Distance mean {}".format(dist_error.avg))
        logger.info("Distance mean calculated between line and predicted point {} pixels, {} mm".format(dist_error_calculated.avg,dist_error_calculated.avg/8)) #8 - 640 pix/80mm

        if config.TRAIN.SWEEP_TRJ_PLOT:

            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.set(xlim=(0, 224), ylim=(0, len(probability)))

            path = np.zeros(0)
            index = np.zeros(0)
            path_target = np.zeros(0)
            index_target = np.zeros(0)
            zs = 0
            for i in range(0, len(X)):
                xs = X[i]
                ys = Y[i]

                if probability[i] > 0.7 and X[i] != 0:  # Spinous
                    color = "r"
                    marker = "o"
                    path = np.append(path, xs)
                    index = np.append(index, i)
                else:  # Gap
                    xs = 0
                    color = "#8c564b"
                    marker = "x"
                plt.title('red - spinous detected, x - Gap', y=1.02, fontsize=10)
                ax.scatter(xs, zs, c=color, marker=marker)

                if probability_label[i] > 0.7 and X_label[i] != 0:  # Spinous
                    color = "b"
                    marker = "o"
                    path_target = np.append(path_target, X_label[i])
                    index_target = np.append(index_target, i)
                else:  # Gap
                    color = "#8c564b"
                    marker = "x"
                ax.scatter(X_label[i], zs, c=color, marker=marker)

                zs = zs + 1
            # ax.plot(path, index,color='c', label="Predicted")
            if config.TEST.PLOT_SMOOTH_LABEL_TRAJECTORY == True:
                steps = np.linspace(0, num_sweep_frames, num=num_sweep_frames)
                # ax.plot(X_label_interpolated,steps, color='m', label="Target")
                ax.plot(X_label_interpolated_smoothed,steps, color='c', label="Target")
                ax.plot(X_pred_interpolated_smoothed, steps, color='m', label="Target")

            ax.plot(path_target, index_target, color='g',label="Target")
            plt.title('red - spinous detected, blue - labelled', y=1.02, fontsize=10)


            # ax1.plot(probability,t_p)
            ax.set_xlabel(' X coordinate')
            ax.set_ylabel(' step')


            '''plot trajectory separately for each target and detected'''
            # plot_path(probability, X, Y,'r')
            # plot_path(probability_label, X_label, Y_label, "b")
            plt.show()


def main():

    try:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.info("STARTING TEST")

        model = utils.model_pose_resnet.get_pose_net(config.TEST.MODEL_FILE, is_train=False)

        if config.TEST.PLOT:

            config.TEST.BATCH_SIZE = 1

        if config.TEST.MODEL_FILE:
            logger.info('=> loading model from {}'.format(config.TEST.MODEL_FILE))
            model.load_state_dict(torch.load(config.TEST.MODEL_FILE, map_location=torch.device('cpu'))['model_state_dict'])
        else:
            logger.info('=> no model found')
        model.eval()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


        if config.TEST.labels_exist:
            test_dir = config.TEST.data_dir
            # test_dataloader = utils.load_test_data(test_dir, 'test', config)
            if config.TRAIN.SWEEP_TRJ_PLOT:
                test_dir = config.TEST.sweep_data_dir
                # test_dataloader = utils.load_test_data(test_dir, '', config)


            print(test_dir)
            criterion = nn.MSELoss()


            model.to(device)

            for patient in ["sweep018_short"]: #test, sweep018_super_short,"sweep20001",sweep18001,sweep018_short,"sweep3013","sweep5005", "sweep9001", Ardit, Farid_F15, Magda, Magda_F10, Maria_T, Maria_V, Javi_F10
                patient_dir = os.path.join(test_dir,patient)
                test_dataloader = utils.load_test_data(patient_dir, '', config)
                val_acc = run_val(model, test_dataloader, device, criterion,logger,config,patient)

        else:
            test_dir = config.TEST.data_dir_w_out_labels
            if config.TRAIN.SWEEP_TRJ_PLOT:
                test_dir = config.TEST.sweep_data_dir
            test_list = [os.path.join(test_dir, item) for item in os.listdir(test_dir)]

            run_test_without_labels(model, test_list, device, logger,config)


    except KeyboardInterrupt:
        out.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':


    main()