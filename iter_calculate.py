import os
import shutil


class AbaqusINPModel(object):
    def __init__(self, inp_filepath):
        self._inp_filepath = inp_filepath
        self._new_inp_filepath = None
        self._new_odb_filepath = None
        self._filename = None
        self._cur_dir = None
        self._iter_dir = None

    def set_up(self):
        self._cur_dir, full_filename = os.path.split(self._inp_filepath)
        self._filename, ext = os.path.splitext(full_filename)

    def get_filename(self):
        return self._filename

    def get_new_inp_filepath(self):
        return self._new_inp_filepath

    def get_new_odb_filepath(self):
        return self._new_odb_filepath

    def create_iter_folder(self):
        # make a iter_inp dir
        self._iter_dir = os.path.normpath(os.path.join(self._cur_dir, 'iter'))
        if os.path.exists(self._iter_dir):
            shutil.rmtree(self._iter_dir)
        os.mkdir(self._iter_dir)

    def update_inp(self, inp_filepath):
        self._inp_filepath = inp_filepath
        self.set_up()

    def generate_inp_from_node_coors_dict(self, inp_name, node_coors_dict):
        node_flag = False
        new_inp_filename = inp_name + '.inp'
        self._new_inp_filepath = os.path.normpath(os.path.join(self._cur_dir, new_inp_filename))
        with open(self._new_inp_filepath, 'w') as fp_writer:
            with open(self._inp_filepath, 'r') as fp_reader:
                while True:
                    line = fp_reader.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line.startswith('*'):
                        fp_writer.write(line)
                        fp_writer.write('\n')
                        if line.lower().startswith('*part'):
                            part_name = line.lower().split(',')[1].split('=')[1]
                        if line.lower().startswith('*node'):
                            node_flag = True
                        else:
                            node_flag = False
                        continue
                    if node_flag:
                        node_id = line.split(',')[0]
                        inst_name = part_name + '-1'
                        node_data = node_coors_dict.get((inst_name, node_id), None)
                        if node_data is None:
                            continue
                        new_node_id = node_data[0]
                        new_node_x = node_data[1]
                        new_node_y = node_data[2]
                        new_node_z = node_data[3]
                        fp_writer.write('%s,    %f,    %f,    %f' % (new_node_id, new_node_x, new_node_y, new_node_z))
                        fp_writer.write('\n')
                    else:
                        fp_writer.write(line)
                        fp_writer.write('\n')
        print "Finish generating inp file %s" % inp_name

    def get_inp_node_coors_dict(self):
        node_flag = False
        inp_node_coors_dict = dict()
        with open(self._inp_filepath, 'r') as fp_reader:
            while True:
                line = fp_reader.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith('*'):
                    if line.lower().startswith('*part'):
                        part_name = line.lower().split(',')[1].split('=')[1]
                        inst_name = part_name + '-1'
                    if line.lower().startswith('*node'):
                        node_flag = True
                    else:
                        node_flag = False
                    continue
                if node_flag:
                    parse_list = line.split(',')
                    node_id = parse_list[0].strip()
                    inp_node_coors_dict[(inst_name, node_id)] = [float(item) for item in parse_list[1:]]
        return inp_node_coors_dict

    def run_inp(self, inp_name, odb_name):
        import job
        full_inp_name = inp_name + '.inp'
        mdb.JobFromInputFile(name=odb_name, inputFileName=full_inp_name)
        mdb.jobs[odb_name].submit()
        mdb.jobs[odb_name].waitForCompletion()
        full_odb_filename = odb_name + '.odb'
        self._new_odb_filepath = os.path.normpath(os.path.join(self._cur_dir, full_odb_filename))
        print 'Solve Done'


class AbaqusODBModel(object):
    def __init__(self, odb_filepath):
        self._odb_filepath = odb_filepath
        self._odb = None

    def set_up(self):
        import odbAccess
        self._odb = odbAccess.openOdb(path=self._odb_filepath)

    def get_result_data_with_instname(self, symbol='U'):
        rst_disp = dict()
        for step_name in self._odb.steps.keys():
            last_frame = self._odb.steps[step_name].frames[-1]
            displacement = last_frame.fieldOutputs[symbol]
            for value in displacement.values:
                inst_name = value.instance.name
                disp_x = value.data[0]
                disp_y = value.data[1]
                disp_z = value.data[2]
                rst_disp[(inst_name.lower(), str(value.nodeLabel))] = [value.nodeLabel, disp_x, disp_y, disp_z]
        return rst_disp

    def get_node_coors_dict_with_instname(self):
        insts = self._odb.rootAssembly.instances
        odb_node_coors = dict()
        for inst_name, nodes_data in insts.items():
            for node in nodes_data.nodes:
                node_id = node.label
                node_x = node.coordinates[0]
                node_y = node.coordinates[1]
                node_z = node.coordinates[2]
                odb_node_coors[(inst_name.lower(), str(node_id))] = [node_id, node_x, node_y, node_z]
        return odb_node_coors


def loop(init_inp_file, dist_odb_file):
    # iter
    dist_node_coors_dict = get_node_coor_dict_by_odb(dist_odb_file)

    inp_model = AbaqusINPModel(init_inp_file)
    inp_model.set_up()

    count = 1
    inp_model.run_inp('blade_init', 'blade_init')
    while True:
        if count == 50:
            break
        tmp_odb_filepath = inp_model.get_new_odb_filepath()
        tmp_node_coors_dict = get_node_coor_dict_by_odb(tmp_odb_filepath)
        rst_data = compare_dicts(tmp_node_coors_dict, dist_node_coors_dict)
        if isinstance(rst_data, bool):
            print count
            break
        assert isinstance(rst_data, list)
        convergence_value = rst_data[0]
        print convergence_value
        node_data_dict = rst_data[1]
        filename = 'iter_%d' % count
        inp_model.generate_inp_from_node_coors_dict(filename, node_data_dict)
        inp_model.run_inp(inp_name=filename, odb_name=filename)
        count += 1


def get_node_coor_dict_by_odb(odb_filepath):
    odb = AbaqusODBModel(odb_filepath)
    odb.set_up()
    return odb.get_node_coors_dict_with_instname()


def compare_dicts(src_dict, dist_dict, alpha=0.2, error=1e-3):
    new_node_data = {}
    convergence_data_list = []

    for key, value in dist_dict.items():
        distance_value = calculate_distance_between_two_point(value, src_dict[key])
        convergence_data_list.append(distance_value)

        diff_x = value[1] - src_dict[key][1]
        diff_y = value[2] - src_dict[key][2]
        diff_z = value[3] - src_dict[key][3]
        node_x = src_dict[key][1] + alpha * diff_x
        node_y = src_dict[key][2] + alpha * diff_y
        node_z = src_dict[key][3] + alpha * diff_z

        new_node_data[key] = [key[1], node_x, node_y, node_z]

    convergence_data_list.sort(reverse=True)
    max_convergence_data_list = convergence_data_list[0:20]

    if max_convergence_data_list[0] <= error:
        return True

    convergence_value = sum(max_convergence_data_list) / len(max_convergence_data_list)

    return [convergence_value, new_node_data]


def calculate_distance_between_two_point(point1, point2):
    import math
    return math.sqrt(math.pow((point1[1]-point2[1]), 2) +
                     math.pow((point1[2]-point2[2]), 2) +
                     math.pow((point1[3]-point2[3]), 2))


if __name__ == "__main__":
    init_inp_file = 'E:/SIMULIA/6.14/Temp/iter/blade_init.inp'
    dist_odb_file = 'E:/SIMULIA/6.14/Temp/iter/blade_code_dist.odb'
    loop(init_inp_file, dist_odb_file)




