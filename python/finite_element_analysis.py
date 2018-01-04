import subprocess
import numpy as np
from numpy import *
import re
class FEA(object):
    """
    ANSYS 求解器

    Parameters
    ----------
    各路径的说明:
    cwd:存储ANSYS_APDL脚本，与ANSYS日志文件
    awd: 此目录为ANSYS的工作目录，所有需要在APDL中读入或输入的文件都在此目录下
    ANSYS_APDL读取文件与写入文件命名规范:
    读取文件:
    material.txt:材料文件,对于各向同性材料：Nx2，第一列杨氏模量，第二列泊松比，N为单元数
    写入文件:
    elements_nodes_counts.txt:单元数与节点数，1x2第一行单元数，第二行节点数
    elements_stiffness.out:未经处理的单元刚度矩阵文件
    elements_nodes.txt: 各单元对应的节点编号,Nx(k+1),N为单元数，第一列单元编号，剩下k列为节点编号
    elements_centers.txt: 各单元的中心坐标，Nx4，N为单元数，第一列为单元编号，其余三列为中心坐标值，（x,y,z)
    elements_volumn.txt: 各单元的体积，Nx2，N为单元数，第一列单元编号，第二列体积
    nodal_solution_u.txt: 节点位移，3列分别表示X,Y,Z方向位移
    nodal_solution_stress.txt: 节点应力，Vonmiss应力，一列，行数等于节点数
    nodal_solution_strain.txt: 节点应变，一列，行数等于节点数
    """
    def __init__(self):
        # 输入文件(APDL)和输出文件都将在cwd目录中，而ANSYS需要的其他输入数据或输出数据的路径，将由ANSYS的APDL指定
        #---------------PC路径--------------------
        self.meshdata_cmd = ["E:\Program Files\ANSYS Inc\\v170\ANSYS\\bin\winx64\MAPDL.exe", '-b', '-i',
               'H:\MaterThesis\ANSYS_SD\APDL_Script\ANSYS_GUI\optimization_simp\get_meshmodel_data.txt', '-o', 'H:\MaterThesis\ANSYS_SD\APDL_Script\ANSYS_GUI\optimization_simp\get_meshmodel_data.out']
        self.result_cmd = ["E:\Program Files\ANSYS Inc\\v170\ANSYS\\bin\winx64\MAPDL.exe", '-b', '-i',
               'H:\MaterThesis\ANSYS_SD\APDL_Script\ANSYS_GUI\optimization_simp\get_result_data.txt', '-o', 'H:\MaterThesis\ANSYS_SD\APDL_Script\ANSYS_GUI\optimization_simp\get_result_data.out']
        self.awd = 'H:/MaterThesis/ANSYS_SD/APDL_Script/ANSYS_GUI/optimization_simp/'
        subprocess.call(self.meshdata_cmd)
        self.element_counts,self.node_counts = self.get_counts(self.awd+'elements_nodes_counts.txt')
        #---------------工作站路径----------------
        # self.meshdata_cmd = ["D:\Program Files\ANSYS2017\ANSYS17.0\ANSYS Inc\\v170\ANSYS\\bin\winx64\MAPDL.exe", '-b', '-i',
        #        'D:\Fengjb\TopologyOptimization\SIMP\get_meshmodel_data.txt', '-o', 'D:\Fengjb\TopologyOptimization\SIMP\get_meshmodel_data.out']
        # self.result_cmd = ["D:\Program Files\ANSYS2017\ANSYS17.0\ANSYS Inc\\v170\ANSYS\\bin\winx64\MAPDL.exe", '-b', '-i',
        #        'D:\Fengjb\TopologyOptimization\SIMP\get_result_data.txt', '-o', 'D:\Fengjb\TopologyOptimization\SIMP\get_result_data.out']
        # self.awd = 'D:/Fengjb/TopologyOptimization/SIMP/'
        # subprocess.call(self.meshdata_cmd)
        # self.element_counts,self.node_counts = self.get_counts(self.awd+'elements_nodes_counts.txt')


    def get_counts(self,element_nodes_file):
        """
        获取单元数和节点数

        Parameters
        ----------
        element_nodes_file:存储单元数和节点数的文件

        Returns
        ----------
        返回单元数和节点数
        """
        counts = loadtxt(element_nodes_file,dtype = int)
        return counts[0],counts[1]


    def generate_material_properties(self,x,penal):
        """
        将OC方法获得的x生成新的材料文件，对于各向异性的点阵材料而言，其材料属性文件将由子类实现

        Parameters
        ----------
        x : 单元密度
        penal : 惩罚因子

        Returns
        ----------
        将生成的材料文件存入material.txt
        """
        nu = 0.3 * np.ones((self.element_counts))
        ex = x**penal
        material = np.array([nu, ex]).T
        np.savetxt(self.awd+"material.txt", material, fmt=' %-.10f', newline='\n')


    def extract_element_stiffness(self,text,dim):
        """提取单元刚度矩阵,提取混合网格单元刚度矩阵，将由子类去解决

        Parameters
        ----------
        text:由ANSYSdebug命令生成的包含单元刚度矩阵的文本
        dim:单元刚度矩阵的维度

        Returns
        ----------
        返回单元刚度矩阵，每一页对应一个单元的刚度矩阵
        """
        K = zeros([self.element_counts, dim, dim])  # numpy 中shape的顺序为页、行、列，轴的顺序与shape的顺序对于，0轴对应页，1轴对于行、2轴对应列
        # 去除Ke中的文字
        ke = re.sub(r' THE BELOW ELEMENT MATRICES AND LOAD VECTORS ARE IN THE NODAL COORDINATE SYSTEMS.\n','',text)
        ke = re.sub(r' GRAVITY AND TRANSIENT EFFECTS ARE INCLUDED.\n\n','',ke)
        ke = re.split(r'STIFFNESS MATRIX FOR ELEMENT[ ]+\d{1,3}[ ]+PLANE182', ke)
        ke = ke[1:]
        ke[-1] = re.split(r'Range', ke[-1])[0]
        # 获取text文本中单元的顺序号
        element_number = self.extract_element_number(text)
        # 生成可以使用的单元刚度矩阵
        i = 0
        for element_stiffness in ke:
            string_type_number = re.split(r'[ ]+', re.sub(r'[ ]\d[ ]', '', element_stiffness))  # 去除Ke中的行号
            for index, item in enumerate(string_type_number[1:-1]):  # 将字符串类型转化成数值型
                string_type_number[index] = float(item)
            fixed_ke = np.array(string_type_number[:-2]).reshape(dim, dim)  # 将1x64的列向量变成8x8的数组
            K[element_number[i] - 1] = fixed_ke
            i = i + 1
        # 返回全部单元的单元刚度矩阵
        return K


    def extract_element_number(self,text):
        """
        获取text文本中单元的顺序号,因为单元刚度矩阵在text中的顺序不是按照单元序号排列的

        Returns
        ----------
        返回text文本中单元顺序
        """
        element = re.findall(r'ELEMENT[ ]+\d{1,3}', text)
        element_numbers = []
        for string in element:
            number = int(re.sub(r'ELEMENT', '', string))
            element_numbers.append(number)
        return element_numbers


    def get_meshmodel_data(self,dim):
        """
        获取有限元模型相关数据,这些数据在迭代计算中属于不变量，只需单独调用该函数一次

        Parameters
        ----------
        dim:单元刚度矩阵的维度

        Returns
        ----------
        K:单元刚度矩阵集合
        element_attributes:单元对应的节点编号
        CENTERS:单元的中心坐标
        V:单元体积
        """
        with open(self.awd+'elements_stiffness.out','r') as f:
            text = f.read()
        K = self.extract_element_stiffness(text,dim)
        element_attributes = loadtxt(self.awd+'elements_nodes.txt', dtype=int)
        CENTERS = loadtxt(self.awd+'elements_centers.txt')
        V = loadtxt(self.awd+'elements_volumn.txt')
        return K,element_attributes,CENTERS,V


    def get_result_data(self,x,penal):
        """
        更新材料密度，进行有限元分析并获取结果数据文件
        """
        self.generate_material_properties(x,penal)
        subprocess.call(self.result_cmd)
        U = loadtxt(self.awd+'nodal_solution_u.txt')
        stress = loadtxt(self.awd+'nodal_solution_stress.txt')
        strain = loadtxt(self.awd+'nodal_solution_strain.txt')
        return U,stress,strain

#单元测试
if __name__=='__main__':
    ansys_solver = FEA()



