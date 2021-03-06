import os
import math
import shutil


class AbaqusModel(object):
    def __init__(self):
        self.keygen = IdGenerator()


class AbaqusINPModel(AbaqusModel):
    def __init__(self, inp_filepath):
        super(AbaqusINPModel, self).__init__()
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
                        inst_name = part_name + '-1'  # just a part vs a instance
                        node_data = node_coors_dict.get(self.keygen.get_id((inst_name, node_id)), None)
                        if node_data is None:
                            continue
                        new_node_id = node_data.id
                        new_node_x = node_data.x
                        new_node_y = node_data.y
                        new_node_z = node_data.z
                        fp_writer.write('%s,    %f,    %f,    %f' % (new_node_id, new_node_x, new_node_y, new_node_z))
                        fp_writer.write('\n')
                    else:
                        fp_writer.write(line)
                        fp_writer.write('\n')
        print "Finish generating inp file %s" % inp_name

    # to do
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
                    if line.lower().startswith('*node'):
                        node_flag = True
                    else:
                        node_flag = False
                    continue
                if node_flag:
                    parse_list = line.split(',')
                    node_id = parse_list[0].strip()
                    inst_name = part_name + '-1'
                    node_x = float(parse_list[1])
                    node_y = float(parse_list[2])
                    node_z = float(parse_list[3])
                    inp_node_coors_dict[self.keygen.get_id((inst_name, node_id))] = NodeData(node_id, node_x, node_y, node_z, instname=inst_name)
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


class AbaqusODBModel(AbaqusModel):
    def __init__(self, odb_filepath):
        super(AbaqusODBModel, self).__init__()
        self._odb_filepath = odb_filepath
        self._odb = None

    def set_up(self):
        import odbAccess
        self._odb = odbAccess.openOdb(path=self._odb_filepath)

    def get_result_data_by_symbol(self, symbol='U'):
        rst_dict = dict()
        for step_name in self._odb.steps.keys():
            last_frame = self._odb.steps[step_name].frames[-1]
            rst = last_frame.fieldOutputs[symbol]
            for value in rst.values:
                inst_name = value.instance.name
                node_id = str(value.nodeLabel)
                comp_x = value.data[0]
                comp_y = value.data[1]
                comp_z = value.data[2]
                rst_dict[self.keygen.get_id((inst_name.lower(), node_id))] = NodeData(node_id, comp_x, comp_y, comp_z, instname=inst_name)
        return rst_dict

    def get_node_coors_dict(self):
        insts = self._odb.rootAssembly.instances
        odb_node_coors = dict()
        for inst_name, nodes_data in insts.items():
            for node in nodes_data.nodes:
                node_id = str(node.label)
                node_x = node.coordinates[0]
                node_y = node.coordinates[1]
                node_z = node.coordinates[2]
                odb_node_coors[self.keygen.get_id((inst_name.lower(), node_id))] = NodeData(node_id, node_x, node_y, node_z, instname=inst_name)
        return odb_node_coors

    def get_deformed_node_coors(self):
        rst_dict = self.get_result_data_by_symbol()
        odb_node_coors_dict = self.get_node_coors_dict()
        deformed_node_coors_dict = dict()
        for key, value in rst_dict.items():
            node_id = value.id
            inst_name = value.instname
            node_x = odb_node_coors_dict[key].x + value.x
            node_y = odb_node_coors_dict[key].y + value.y
            node_z = odb_node_coors_dict[key].z + value.z
            deformed_node_coors_dict[self.keygen.get_id((inst_name.lower(), node_id))] = NodeData(node_id, node_x, node_y, node_z, instname=inst_name)
        return deformed_node_coors_dict


class NodeData(object):
    def __init__(self, id, x, y, z, partname=None, instname=None):
        self._id = id
        self._x = x
        self._y = y
        self._z = z
        self._partname = partname
        self._instname = instname

    @property
    def id(self):
        return self._id

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def z(self):
        return self._z

    @property
    def instname(self):
        return self._instname

    @property
    def partname(self):
        return self._partname


class IdGenerator(object):
    def __init__(self, start=1):
        self._dic_uuid_id = dict()
        self._set_ids = set()
        self._max_id = start-1

    def get_id(self, uuid, default=None):
        if uuid in self._dic_uuid_id:
            return self._dic_uuid_id[uuid]

        newid = None
        try:
            newid = int(uuid)
        except:
            if default is not None:
                try:
                    newid = int(default)
                except:
                    pass

        if newid is None or newid in self._set_ids:
            newid = self._max_id + 1

        self._dic_uuid_id[uuid] = newid
        self._set_ids.add(newid)

        self._max_id = max(self._max_id, newid)
        return self._dic_uuid_id[uuid]


class Calculate(object):
    def __init__(self, init_inp_file, dist_inp_file):
        self._init_inp_file = init_inp_file
        self._dist_inp_file = dist_inp_file
        self._dist_node_coors_dict = dict()
        self._new_node_coors_dict = dict()
        self._is_same = False
        self._convergence_value = 0.0

    def loop(self, iter_max_step=200):

        dist_inp_model = AbaqusINPModel(self._dist_inp_file)
        dist_inp_model.set_up()
        self._dist_node_coors_dict = dist_inp_model.get_inp_node_coors_dict()

        # iter
        inp_model = AbaqusINPModel(self._init_inp_file)
        inp_model.set_up()
        inp_filename = inp_model.get_filename()
        inp_model.run_inp(inp_filename, 'init')

        count = 1
        while True:
            if count > iter_max_step:
                break
            iter_odb_filepath = inp_model.get_new_odb_filepath()
            iter_odb = AbaqusODBModel(iter_odb_filepath)
            iter_odb.set_up()
            cur_inp_node_coors_dict = iter_odb.get_node_coors_dict()
            deformed_node_coors_dict = iter_odb.get_deformed_node_coors()
            self.update_node_dict(cur_inp_node_coors_dict, deformed_node_coors_dict)
            if self._is_same:
                break
            print self._convergence_value
            filename = 'iter_%d' % count
            inp_model.generate_inp_from_node_coors_dict(filename, self._new_node_coors_dict)
            inp_model.run_inp(inp_name=filename, odb_name=filename)
            count += 1

    def update_node_dict(self, cur_inp_node_coors_dict, deformed_node_coors_dict, alpha=0.08, error=1e-3):
        nodes_distance_data_list = []

        for key, dist_node_data in self._dist_node_coors_dict.items():
            deformed_node_data = deformed_node_coors_dict[key]
            distance_value = self.calculate_distance_between_two_nodes(dist_node_data, deformed_node_data)
            nodes_distance_data_list.append(distance_value)

            node_id = dist_node_data.id
            inst_name = dist_node_data.instname
            diff_x = dist_node_data.x - deformed_node_data.x
            diff_y = dist_node_data.y - deformed_node_data.y
            diff_z = dist_node_data.z - deformed_node_data.z
            if node_id == '18208':
                print dist_node_data.x, dist_node_data.y, dist_node_data.z
                print deformed_node_data.x, deformed_node_data.y, deformed_node_data.z
                print diff_x, diff_y, diff_z
            node_x = cur_inp_node_coors_dict[key].x + alpha * diff_x
            node_y = cur_inp_node_coors_dict[key].y + alpha * diff_y
            node_z = cur_inp_node_coors_dict[key].z + alpha * diff_z

            self._new_node_coors_dict[key] = NodeData(node_id, node_x, node_y, node_z, instname=inst_name)

        nodes_distance_data_list.sort(reverse=True)
        max_nodes_distance_data_list = nodes_distance_data_list[0:20]

        if max_nodes_distance_data_list[0] <= error:
            self._is_same = True

        self._convergence_value = sum(max_nodes_distance_data_list) / len(max_nodes_distance_data_list)

    def calculate_distance_between_two_nodes(self, node1, node2):
        return math.sqrt(math.pow((node1.x - node2.x), 2) +
                         math.pow((node1.y - node2.y), 2) +
                         math.pow((node1.z - node2.z), 2))


if __name__ == "__main__":
    init_inp_file = 'E:/SIMULIA/6.14/Temp/iter_all/blade_init.inp'
    dist_inp_file = 'E:/SIMULIA/6.14/Temp/iter_all/blade_code_dist.inp'

    cal = Calculate(init_inp_file, dist_inp_file)
    cal.loop()



