import numpy as np
import cv2
import time
import fundmental as fun
import wavelet as wave
import baseFun as bs
import kd_tree as kd
import GaussFit as gs
import os
import matplotlib.pyplot as plt
import mrc2jpg as mj
import sys
import mrcfile as mf
import math


# 此代码中有全局变量：img_2value,radius_int,mrc_file
def template_make(img: np.ndarray, scale: int):
    """
    该流程中的img像素是正的（取反操作并入了waveletprocess）
    wave_img有两次去除点，一次去除小于4或者8的点，第二次去除小于直径的0.8倍的点
    :param img:
    :return:
    """
    margin = 2  # the margin of template of fiducial marker
    # j = 3
    j = scale + 1
    threshold_pixel = 0.5
    threshold_shape = 0.75  # 0.85
    img_m, img_n = img.shape
    # threshold_remove = 4 if min(img_n, img_m) < 2000 else 8
    threshold_remove = 4 if min(img_n, img_m) < 1500 else 8
    img = bs.normalize(img)

    wave_image, __ = wave.waveletprocess2(Image=img, J=j)
    wave_ori = fun.hardval2(wave_image, 2)
    img_2value = wave_ori.copy()
    fun.removeSmall(img_2value, threshold_remove)
    if save_img:
        if wave_ori.dtype == 'float32':
            wave_ori_temp = (wave_ori * 255).astype(np.uint8)
            cv2.imwrite(f"{result_folder}/wave_original_img_{save_name}", wave_ori_temp)
        else:
            cv2.imwrite(f"{result_folder}/wave_original_img_{save_name}", wave_ori)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(img_2value, connectivity=8, ltype=None)

    center_int = centroids.astype(int)
    fid_index = []
    # fid_circle = []
    for i in range(1, num_labels):
        sub_img = img[stats[i, 1]:stats[i, 1] + stats[i, 3] + 1, stats[i, 0]:stats[i, 0] + stats[i, 2]]
        sub_wave = img_2value[stats[i, 1]:stats[i, 1] + stats[i, 3] + 1, stats[i, 0]:stats[i, 0] + stats[i, 2]]
        mean, dev = cv2.meanStdDev(sub_img)

        # remove1: remove the sub_cubic by pixel，判断sub_img中点，均值mean，方差dev是否会合适
        if sub_img[center_int[i, 1] - stats[i, 1], center_int[i, 0] - stats[
            i, 0]] > threshold_pixel or mean > threshold_pixel or dev < 0.05:
            # print(f'点{stats[i,1]},{stats[i,0]}是因为remove1而丢掉')
            # if sub_img[center_int[i, 1] - stats[i, 1], center_int[i, 0] - stats[
            # i, 0]] > threshold_pixel:
            #     print(f'是像素值中间的点不符合')
            # if mean > threshold_pixel:
            #     print(f'是像素均值不符合的问题')
            # if dev < 0.1:
            #     print('是方差不符合')
            continue

        # remove2: remove the roundness too small,第一个判断是把十分不合理的从小波图去除，第二个判断更强，表示可以用作模板的patches的要求更高
        round = bs.roundness(sub_wave)
        if round <= threshold_shape: 
            # print(f'点{stats[i,1]},{stats[i,0]}是因为remove2而丢掉')
            continue

        fid_index.append(i)

    # 对得到的fid_index进行统计直径
    d = []
    for i in fid_index:
        d.append(max(stats[i, 2], stats[i, 3]))

    # 进一步精确小波图（把像素点个数小于
    if len(d) == 0:
        print('The wavelet detailed coefficients do not get proper information.')
        print('Please select the scale again.')
        return (0, 0, 0)
    d_mean = sum(d) / len(d)
    fun.removeSmall(img_2value, int(d_mean * 0.8))
    if show_img:
        fun.draw(wave_image, 'wave_image')
        fun.draw(img_2value, 'img_2value')
    if save_img:
        if img_2value.dtype == 'float32':
            wave_img2_temp = (img_2value * 255).astype(np.uint8)
            cv2.imwrite(f'{result_folder}/wave_img_{save_name}', wave_img2_temp)
        else:
            cv2.imwrite(f'{result_folder}/wave_img_{save_name}', img_2value)

    hist, arr = np.histogram(d, bins=10, range=(min(d), max(d)))
    max_index = np.where(hist == max(hist))[0]
    max_index = max_index[0]
    diameter_float = (arr[max_index] + arr[max_index + 1]) / 2
    temp = int(diameter_float)
    d_end = temp + 2 * margin if temp % 2 == 1 else temp + 1 + 2 * margin
    r_end = int((d_end / 2) + 0.5)

    # 得到最终模板
    add_template = np.zeros(shape=(2 * r_end + 1, 2 * r_end + 1), dtype=np.float32)
    num_template = 0
    for i in fid_index:
        # 判断是否是边缘点
        if center_int[i, 1] - r_end < 0 or center_int[i, 0] - r_end < 0 or center_int[i, 1] + r_end + 1 > img_m or \
                center_int[i, 0] + r_end + 1 > img_n:
            continue
        temp = img[center_int[i, 1] - r_end:center_int[i, 1] + r_end + 1,
               center_int[i, 0] - r_end:center_int[i, 0] + r_end + 1]
        # fun.draw(temp, f'temp_of_{i}')
        add_template = cv2.add(temp, add_template)
        num_template += 1

    if num_template==0:
        return 0,0,0
    template = add_template / num_template
    wavelet_image = img_2value
    return template, wavelet_image, d_end


def wavelet_make_no_template(img, scale):
    """
    Only wavelet coefficients
    """
    margin = 2  # the margin of template of fiducial marker
    # j = 3
    j = scale + 1
    img_m, img_n = img.shape
    # threshold_remove = 4 if min(img_n, img_m) < 2000 else 8
    threshold_remove = 4 if min(img_n, img_m) < 1500 else 8
    img = bs.normalize(img)

    wave_image, __ = wave.waveletprocess2(Image=img, J=j)
    wave_ori = fun.hardval2(wave_image, 2)
    img_2value = wave_ori.copy()
    fun.removeSmall(img_2value, threshold_remove)
    if save_img:
        if wave_ori.dtype == 'float32':
            wave_ori_temp = (wave_ori * 255).astype(np.uint8)
            cv2.imwrite(f"{result_folder}/wave_original_img_{save_name}", wave_ori_temp)
        else:
            cv2.imwrite(f"{result_folder}/wave_original_img_{save_name}", wave_ori)
    return img_2value


def template_average(template: np.ndarray):
    """
    This function used to average template to make the center point more center
    :param template:
    :return:
    """
    # dividing height and width by 2 to get the center of the image
    height, width = template.shape[:2]

    # get the center coordinates of the image to create the 2D rotation matrix
    center = ((width - 1) / 2, (height - 1) / 2)

    # using cv2.getRotationMatrix2D() to get the rotation matrix
    rotate_matrix = cv2.getRotationMatrix2D(center=center, angle=90, scale=1)

    # rotate the image using cv2.warpAffine
    rotated_image1 = cv2.warpAffine(src=template, M=rotate_matrix, dsize=(width, height))
    rotated_image2 = cv2.warpAffine(src=rotated_image1, M=rotate_matrix, dsize=(width, height))
    rotated_image3 = cv2.warpAffine(src=rotated_image2, M=rotate_matrix, dsize=(width, height))

    template_new = np.add(template, rotated_image1)
    template_new = np.add(template_new, rotated_image2)
    template_new = np.add(template_new, rotated_image3)
    template_new = template_new / 4
    return template_new


def get_ave_pixel(img, seed_x, seed_y, r):
    """
    找某点周围的像素均值
    :param img: 图像
    :param seed_x: 小方块左上角点对应x
    :param seed_y: 小方块左上角点对应y
    :param r: 方块半径
    :return: 方块中心点附近像素均值
    """
    # m, n = img.shape
    d = 2 * r + 1
    thre_r = float(r * r) * 0.36  # 0.9r
    center_x = seed_x + r
    center_y = seed_y + r
    value = 0.
    count = 0
    for x in range(seed_x, seed_x + d):
        # if x >= n:
        #     pass
        for y in range(seed_y, seed_y + d):
            # if y1 >= m:
            #     pass
            if (center_x - x) * (center_x - x) + (center_y - y) * (center_y - y) < thre_r:
                value += img[y, x]
                count += 1
    return value / count


def refine_fid_by_gaussian_distribution_markerauto_wave(candidate):
    """
    利用ncc*pixel的分布筛选candidate
    :param candidate:坐标集合，[x,y1,ncc,pixel,none,index]
    :return:new_fid每一维数据分别是(x,y1,ncc,avg_pixel,ncc*avg_pixel,index)
    """
    # 构造ncc*pixel
    num = len(candidate)
    new_score = []  # new_score是评分的指标
    for i in range(num):
        new_score.append(candidate[i][2] * candidate[i][3])

    # # 构造new_score的均值与标准差
    new_score_np = np.array(new_score)
    avg = np.mean(new_score_np)
    stdev = np.std(new_score_np)

    # 开始筛选
    thre = avg - 0.5 * stdev

    if show_plt:
        temp, _ = np.histogram(new_score, bins=50)
        max_temp = max(temp)
        max_temp = int(1.1*max_temp)
        fig, axes = plt.subplots()
        axes.hist(new_score, bins=50)
        axes.vlines(thre, 0, max_temp, linestyles='dashed', colors='red', label=r'$\mu_{np}-0.5\sigma_{np}$')
        axes.set_xlabel(r"NCC$\times$pixel")
        axes.set_ylabel(f"Number")
        axes.set_title(f"Distribution of candidates in {file_name.split('.')[0]}")
        axes.legend()
        fig.show()

    new_fid = []
    fid_index = 0
    for i in range(num):
        if new_score[i] > thre:
            new_fid.append(
                [candidate[i][0], candidate[i][1], candidate[i][2], candidate[i][3], new_score[i], fid_index])
            fid_index += 1
    return new_fid


def refine_fid_by_gaussian_distribution_markerauto_no_wave(candidate):
    """
    利用ncc*pixel的分布筛选candidate
    :param candidate:坐标集合，[x,y1,ncc,pixel,none,index]
    :return:new_fid每一维数据分别是(x,y1,ncc,avg_pixel,ncc*avg_pixel,index)
    """
    # 构造ncc*pixel
    num = len(candidate)
    # print(f"The number of candidates without information in {file_name} is {num}")
    new_score = []  # new_score是评分的指标
    for i in range(num):
        new_score.append(candidate[i][2] * candidate[i][3])

    # # 构造new_score的均值与标准差
    new_score_np = np.array(new_score)
    avg = np.mean(new_score_np)
    stdev = np.std(new_score_np)

    # 开始筛选
    thre = avg + 3 * stdev

    if show_plt:
        temp, _ = np.histogram(new_score, bins=50)
        max_temp = max(temp)
        max_temp = int(1.1*max_temp)
        fig, axes = plt.subplots()
        axes.hist(new_score, bins=50)
        axes.vlines(thre, 0, max_temp, linestyles='dashed', colors='red', label=r'$\mu_{np}+3\sigma_{np}$')
        axes.set_xlabel(r"NCC$\times$pixel")
        axes.set_ylabel(f"Number")
        axes.set_title(f"Distribution of candidates without information in {file_name.split('.')[0]}")
        axes.legend()
        fig.show()

    new_fid = []
    fid_index = 0
    for i in range(num):
        if new_score[i] > thre:
            new_fid.append(
                [candidate[i][0], candidate[i][1], candidate[i][2], candidate[i][3], new_score[i], fid_index])
            fid_index += 1
    return new_fid


def draw_point(img: np.ndarray, cubic_points: list, r: int, color: tuple = (0, 255, 0)):
    """
    将cubic的点在画标注
    :param img:
    :param cubic_points: 方格的左上角
    :param r: 2r+1为方格长度
    :return:
    """
    if not cubic_points.any():
        return 0
    num = len(cubic_points)
    if img.dtype == 'float32':
        for i in range(num):
            cv2.circle(img, (cubic_points[i][0], cubic_points[i][1]), r, (1., 1., 1.))
    else:
        for i in range(num):
            cv2.circle(img, (cubic_points[i][0], cubic_points[i][1]), r, color)
    if show_img:
        fun.draw(img, "in draw_point function")


def remove_by_ncc_in_end(fid):
    """
    filter by ncc in the end
    """
    new_fid = []
    ncc_threshold = 0.55
    index = 0
    for i in range(len(fid)):
        if fid[i][2]>=ncc_threshold:
            temp = fid[i]
            temp[5] = index
            index += 1
            new_fid.append(temp)
    return new_fid

def markerauto_work_flow(img_ori: np.ndarray, template_ori: np.ndarray):
    """
    markerauto
    :param img_ori:
    :param template_ori:
    :return:
    """
    img_draw = cv2.cvtColor(img_ori, cv2.COLOR_GRAY2RGB)
    # =======================
    # pre-processing
    # 归一化与取反操作
    img = bs.normalize(img_ori)
    img = fun.Img_in2(img)

    template = bs.normalize(template_ori)
    template = fun.Img_in2(template)

    # ======================
    # 模板匹配并归一化
    corr = cv2.matchTemplate(img, template, 3)
    corr = bs.normalize(corr)

    # ======================
    # Candidiate generation
    start_time = time.time()
    img_mean, img_std_dev = cv2.meanStdDev(img)
    corr_mean, corr_std_dev = cv2.meanStdDev(corr)

    img_threshold = int(img_mean*10)/10
    corr_threshold = int((corr_mean + 2 * corr_std_dev)*10)/10

    idiameter = int(2 * radius_int + 1)

    candidate_no_wave = []
    candidate_wave = []
    no_index = 0
    wave_index = 0
    img_draw_temp = img_draw.copy()
    corr_m, corr_n = corr.shape
    remove_point = []
    for i in range(0, corr_m, idiameter):
        for j in range(0, corr_n, idiameter):
            peak_m, peak_n = bs.find_local_peak(corr, i, j, idiameter, idiameter)
            if corr[peak_m, peak_n] > corr_threshold and get_ave_pixel(img, peak_n, peak_m, radius_int) > img_threshold:
                if 255 in wave_img[peak_m:peak_m + 2 * radius_int + 1, peak_n:peak_n + 2 * radius_int + 1]:
                    candidate_wave.append(
                        [peak_n, peak_m, corr[peak_m, peak_n], get_ave_pixel(img, peak_n, peak_m, radius_int), 1,
                         wave_index])
                    
                    wave_index += 1
                    cv2.circle(img_draw_temp, (peak_n + radius_int, peak_m + radius_int), radius_int,
                               (0, 255, 0))
                else:
                    candidate_no_wave.append(
                        [peak_n, peak_m, corr[peak_m, peak_n], get_ave_pixel(img, peak_n, peak_m, radius_int), 1,
                         no_index])
                    # fids = [x, y1, corr, pixel, none, index]
                    no_index += 1
                    cv2.circle(img_draw_temp, (peak_n + radius_int, peak_m + radius_int), radius_int,
                               (0, 0, 255))
            else:
                # print(f"==========")
                # print(f"点{peak_n,peak_m}将被去除")
                # if corr[peak_m, peak_n] <= corr_threshold:
                #     print(f"该块的峰值corr不大于{corr_threshold}")
                # if get_ave_pixel(img, peak_n, peak_m, radius_int) <= img_threshold:
                #     print(f"该块的平均像素值不大于{img_threshold}")
                remove_point.append([peak_n, peak_m])

    if save_img:
        if img_draw_temp.dtype == 'float32':
            img_draw_temp = (255 * img_draw_temp).astype(np.uint8)
            cv2.imwrite(f'{result_folder}/candidate1_generation_{save_name}', img_draw_temp)
        else:
            cv2.imwrite(f'{result_folder}/candidate1_generation_{save_name}', img_draw_temp)

    fid_no_wave = candidate_no_wave
    fid_wave = candidate_wave
    end_time = time.time()
    information_file.write(f"The time of the second module is {end_time - start_time}.\n")
    information_file.write(
        f"The number of fiducial markers in the second module is {len(candidate_wave) + len(candidate_no_wave)}\n")

    # ==============================
    # step1 Gaussian distribution
    start_time = time.time()
    new_fid_no_wave = refine_fid_by_gaussian_distribution_markerauto_no_wave(fid_no_wave)
    new_fid_temp = new_fid_no_wave + fid_wave
    new_fid = refine_fid_by_gaussian_distribution_markerauto_wave(new_fid_temp)
    # fid元素解释： fid=(x,y1,ncc,avg_pixel,ncc*avg_pixel,index)
    if save_img:
        img_draw_temp = img_draw.copy()
        location_xy2 = np.array(new_fid)[:, :2].astype(int) + radius_int
        draw_point(img_draw_temp, location_xy2, radius_int, color=(0, 255, 0))

        if img_draw_temp.dtype == 'float32':
            img_draw_temp = (255 * img_draw_temp).astype(np.uint8)
            cv2.imwrite(f'{result_folder}/candidate2_gauss_{save_name}', img_draw_temp)
        else:
            cv2.imwrite(f'{result_folder}/candidate2_gauss_{save_name}', img_draw_temp)
    end_time = time.time()
    information_file.write(
        f"The time of the third module is {end_time - start_time}\n")
    information_file.write(f"The number of fidicual markers in the third module is {len(new_fid)}\n")
    fid = new_fid


    # ==========================
    # step2 NCC filter in the end
    new_fid = remove_by_ncc_in_end(fid=fid)
    fid = new_fid
    # ========================
    # Remove repeated kd tree
    # 请确保fid的第5个元素是目前fid的index
    candidate_index_location = 5  # fid 的第几个分量为index
    start_time = time.time()
    img_draw_temp = img_draw.copy()

    dist_thr = diameter_int  # *1.414
    node = kd.Node()
    new_fid = []
    kd.construct(d=2, data=fid.copy(), node=node, layer=0)
    for i in range(len(fid)):
        if fid[i][4] < 0:
            continue
        L = []  # 用来保存该点的最近邻
        kd.search(node=node, p=fid[i], L=L, K=5)
        for j in range(len(L)):
            if kd.distance(fid[i], L[j]) < dist_thr:
                fid[int(L[j][candidate_index_location])][4] = -1
        new_fid.append(fid[i])
        cv2.circle(img_draw_temp, [fid[i][0] + radius_int, fid[i][1] + radius_int], radius_int, (0, 255, 0))
        kd.clear_flag(node=node)
    fid = new_fid
    if show_img:
        fun.draw(img_draw_temp, "remove repeat")
    if save_img:
        if img_draw_temp.dtype == 'float32':
            img_draw_temp = (255 * img_draw_temp).astype(np.uint8)
            cv2.imwrite(f'{result_folder}/candidate3_repeat_{save_name}', img_draw_temp)
        else:
            cv2.imwrite(f'{result_folder}/candidate3_repeat_{save_name}', img_draw_temp)
    end_time = time.time()

    fid = np.array(fid)
    return fid


def location_fid(img: np.ndarray, location: np.ndarray, width: int):
    """
    标记点定位阶段
    :param img: 定位的原图片
    :param location: 识别阶段的坐标点,都为左上角
    :param width: 进行圆心refine的子图的大小
    :return:refined_xy, 定位后fids的坐标
    """
    location = location.astype(int)
    img_inv = fun.Img_in(img)
    refined_xy = []
    score_xy = []
    for i in range(len(location)):
        sub_img = img_inv[location[i, 1]:location[i, 1] + width, location[i, 0]:location[i, 0] + width]
        if 0 in sub_img:
            sub_img[sub_img == 0] = 2

        row, colum, sigma, para_a = gs.compute_center_Gauss(sub_img)
        real_row = row + location[i, 1]
        real_colum = colum + location[i, 0]
        refined_xy.append(np.array([real_colum, real_row], dtype=int))
        score = gs.compute_gauss_error(sub_img, row, colum, sigma, para_a)
        score_xy.append(score)
    score_xy = np.array(score_xy)
    refined_xy = np.array(refined_xy)
    return refined_xy, score_xy


def main(root_dir, projection, agle, dense, scale, result_folder):
    global template1, mrc_file, wave_img, radius_int, diameter_int, show_img, save_img, show_plt, fids_file, information_file

    # input dataset
    # c
    # root_dir = input("Mrc file path:")
    # agle = eval(input("The index of the image you want to detect:"))
    # root_dir = '/media/haley/Expansion/ETdata/ShiWT001/ShiWT001.mrc'
    # root_dir = '/media/haley/Expansion/ETdata/110001/110001.st'
    # root_dir = '/media/haley/Expansion/ETdata/70001/70001.st'
    # agle = 21
    # projection = mj.get_mrc_file_in_fixed_angle_and_save(root_dir, angle=agle)

    # mean = np.mean(projection)
    # std = np.std(projection)
    # projection = projection.copy()
    # projection[projection>mean+4*std] = mean + 4*std
    # ori_img = cv2.normalize(projection, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    ori_img = projection
    # file_name = root_dir.split('/')[-1]
    # save_name = file_name.split('.')[0]+'.jpg'

    # result_folder = f"./result_{time.strftime('%m-%d-%H-%M-%S', time.localtime(time.time()))}"
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)

    python_file_name = os.path.basename(__file__)

    # information_file used to save information
    information_file = open(f"{result_folder}/general_information.txt", "a")
    information_file.write(f"Time：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}\n")
    information_file.write(f"The program file is {python_file_name}.\n")
    information_file.write(f"The input mrc_file is {file_name} ... \n")
    information_file.write(f"The selected angle is {agle}.\n")
    print(f'The input mrc_file is {save_name} ...')
    fids_file = open(f"{result_folder}/fiducial_{file_name.split('.')[0]}.txt", "w")

    # Pre-process
    # ori_img = cv2.imread(mrc_file, 0)
    if ori_img is None:
        print(f'There is no figure {file_name}!')
        sys.exit(0)
    if show_img:
        fun.draw(ori_img, "The input image")
    information_file.write(f"The shape of the projection is {ori_img.shape}.\n")
    # print(f'The shape of original image is {ori_img.shape}.')
    # dense = eval(input(f"Dose {file_name} contain more than 50 fiducial markers? \nIf yes, please input 1, otherwise input 0."))
    # print("The scale of detailed coefficients should be provided.")
    # print("The scale is usually chosen as 2 or 3. 2 will be better.")
    # scale = eval(input("The scale of detailed coefficients you select is:"))
    if dense:
        size = 2500
    else:
        size = 2000
    # size = 2000
    m, n = ori_img.shape
    min_shape = min(m, n)
    # check if it is empty and too big to detect
    resize_index = 0
    if min_shape > size:
        for i in range(2, 10, 2):
            if int(min_shape / i) > size:
                continue
            else:
                mul_para = i  # parameter of resize
                resize_index = 1
                break
        img_resized = cv2.resize(ori_img, dsize=(int(n / mul_para), int(m / mul_para)),
                                 interpolation=cv2.INTER_AREA)
    else:
        img_resized = ori_img
        mul_para = 1

    if show_img:
        fun.draw(img_resized, 'After resize')

    # detection start
    print("The detection step begins...")
    start = time.time()
    img = cv2.GaussianBlur(img_resized, (5, 5), 0)
    img1 = fun.ToOne(img)

    wave_img = wavelet_make_no_template(img, scale)
    # statistic of NCC pixel and contrast to get the threshold
    fid = markerauto_work_flow(img, template1)
    end = time.time()
    information_file.write(f"The number of detected fiducial markers in detection step is {len(fid)}.\n")
    information_file.write(f"The time of detection step is {end-start}\n")
    print(f"The time of detection step is {end-start}")
    # reture the location of original image
    ori_fid = fid * mul_para

    # location the fids
    print("The fiducial marker localization step begins...")
    start = time.time()
    temp_ori_m = ori_template.shape[0]
    fid, score_error = location_fid(ori_img, ori_fid, temp_ori_m)
    end = time.time()
    print(f"The time of fiducial markers localization step is {end-start}")
    information_file.write(f"The time of fiducial markers localization step is {end-start}\n")
    # ori_img_draw = cv2.equalizeHist(ori_img)
    ori_img_draw = cv2.cvtColor(ori_img,cv2.COLOR_GRAY2BGR)
    for i in range(len(fid)):
        fids_file.write(f"{fid[i]}\n")
        cv2.circle(ori_img_draw, fid[i], int(radius_int*mul_para), (0, 255, 0))

    cv2.imwrite(f"./{result_folder}/end_{save_name}", ori_img_draw)
    fids_file.close()
    information_file.close()
    return 1


if __name__=="__main__":
    # root_dir = '/media/haley/Expansion/ETdata/110001/110001.st'
    # root_dir = '/media/haley/Expansion/ETdata/70001/70001.st'
    # root_dir = '/media/haley/Expansion/ETdata/20160914_YWC216_10004/20160914_YWC216_10004.st'
    # root_dir = '/media/haley/Expansion/ETdata/10111/data/14dec27a_WTCampy_002.mrc'
    # root_dir = '/media/haley/Expansion/ETdata/corey/V4B_G1_Tilt2.mrc'
    root_dir = '/media/haley/Expansion/ETdata/20160914_YWC216_10007/20160914_YWC216_10007.st'
    # root_dir = '/media/haley/Expansion/ETdata/20160914_YWC216_10016/20160914_YWC216_10016.st'
    # root_dir = '/media/haley/Expansion/ETdata/11kx_3bin2ax4/11kx_3bin2ax4.st'
    # root_dir = '/media/haley/Expansion/ETdata/tutorialData/BBa.st'
    # root_dir = '/media/haley/Expansion/ETdata/nmar20024-bug-fids_detect/nmar20024.st'
    # root_dir = '/media/haley/Expansion/ETdata/ShiWT001/ShiWT001.mrc'
    # root_dir = '/media/haley/Expansion/ETdata/corey/V4B_G1_Tilt2.mrc'

    # root_dir = '/media/haley/Expansion/data/new_data/new/09dec31a_B864b_024_projections.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/new/09dec31a_B864b_026_projections.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/11dec14_MEFsB_0005_projections.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/11dec14_MEFsB_0006_projections.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/11dec14_MEFsB_0007_ns_projections.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/new/12jan05_AT1BT1_0005_projections.mrc' 
    # root_dir = '/media/haley/Expansion/data/new_data/12jan05_AT1BT1_new.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/new/12jan05_MEFsB_AT2BT1_0021_projections.mrc' 
    # root_dir = '/media/haley/Expansion/data/new_data/2017_YWC259_10019_new.mrc'
    # root_dir = '/media/haley/Expansion/data/new_data/new/20170706_YWC259_10019_projections.mrc' 
    show_img = 0
    save_img = 1
    show_plt = 0


    num_projection = 121
    num_center = 0
    dense = 1
    scale = 2

    result_folder = f"./result_{num_center}"
    if not os.path.exists(result_folder):
        os.mkdir(f"{result_folder}")
    file_name = root_dir.split('/')[-1]
    save_name = file_name.split('.')[0]+'.jpg'

    mrc_file = mf.open(root_dir)
    mrc_data = mrc_file.data
    projection = mrc_data[num_center].copy()
    pro_mean = np.mean(projection)
    pro_std = np.std(projection)
    projection[projection>pro_mean+4*pro_std] = pro_mean + 4*pro_std
    projection[projection<pro_mean-4*pro_std] = pro_mean - 4*pro_std
    projection = cv2.normalize(projection, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # scale = eval(input("The scale of detailed coefficients you select is:"))
    if dense:
        size = 2500
    else:
        size = 2000
    # size = 2000
    m, n = projection.shape
    min_shape = min(m, n)
    # check if it is empty and too big to detect
    resize_index = 0
    if min_shape > size:
        for i in range(2, 10, 2):
            if int(min_shape / i) > size:
                continue
            else:
                mul_para = i  # parameter of resize
                resize_index = 1
                break
        img_resized = cv2.resize(projection, dsize=(int(n / mul_para), int(m / mul_para)),
                                 interpolation=cv2.INTER_AREA)
    else:
        img_resized = projection
        mul_para = 1

    if show_img:
        fun.draw(img_resized, 'After resize')

    # detection start
    print("The detection step begins...")
    img = cv2.GaussianBlur(img_resized, (5, 5), 0)
    img1 = fun.ToOne(img)

    # Template generation
    template1, wave_img, diameter_int = template_make(img, scale)
    if not diameter_int:
        print(f"There is nothing information catched in the center image of {root_dir}")
        sys.exit(0)

    try:
        m, n = template1.shape
    except AttributeError:
        print(f'Now we will passed it.')  # This means tempalte generation was wrong.
        sys.exit(0)
    template1 = template_average(template1)
    ori_template = cv2.resize(template1, dsize=(int(mul_para * m), int(mul_para * n)),
                              interpolation=cv2.INTER_AREA)
    if show_img:
        fun.draw(wave_img, "output wave_image of template_make")
        fun.draw(template1, "template made from template_make")
    if save_img:
        if ori_template.dtype == 'float32':
            template_temp = (255 * ori_template).astype(np.uint8)
            cv2.imwrite(f'{result_folder}/template_{save_name}', template_temp)
        else:
            cv2.imwrite(f'{result_folder}/template_{save_name}', ori_template)

    # diameter_int = diameter_temp * mul_para
    radius_int = int(diameter_int / 2 + 0.5)


    for angle in range(num_projection):
            projection = mrc_data[angle].copy()
            pro_mean = np.mean(projection)
            pro_std = np.std(projection)
            projection[projection>pro_mean+4*pro_std] = pro_mean + 4*pro_std
            projection[projection<pro_mean-4*pro_std] = pro_mean - 4*pro_std
            projection = cv2.normalize(projection, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            result_folder = f"./result_{angle}"
            file_name = root_dir.split('/')[-1]
            save_name = file_name.split('.')[0]+'.jpg'
            
            key = main(root_dir=root_dir,projection=projection, agle=angle, dense=dense, scale=scale, result_folder = result_folder)
            if not key:
                print('High-quality templates suitable for this dataset are difficult to extract. ')
