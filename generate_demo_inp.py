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

    def get_node_coors_dict(self):
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
                        part_name = line.split(',')[1].split('=')[1]
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

    def generate_inp_from_inst_to_part(self, inp_name, odb_filepath):
        odb_model = AbaqusODBModel(odb_filepath)
        odb_model.set_up()
        node_coors_dict = odb_model.get_node_coors_dict_with_instname()
        node_flag = False
        instance_flag = False
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
                        line = line.lower()
                        if line.startswith('*part'):
                            part_name = line.split(',')[1].split('=')[1]
                        if line.startswith('*node'):
                            node_flag = True
                        else:
                            node_flag = False

                        if line.startswith('*instance'):
                            if line.split(',')[2].split('=')[1] in ['c-copy', 'd-copy']:
                                instance_flag = True
                            else:
                                instance_flag = False
                        if line.startswith('*end instance'):
                            instance_flag = False
                        continue
                    if instance_flag:
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

    def generate_inp_from_odb(self, inp_name, odb_filepath):
        odb_model = AbaqusODBModel(odb_filepath)
        odb_model.set_up()
        rst_disp = odb_model.get_result_data_with_instname()
        node_flag = False
        new_inp_filename = inp_name + '.inp'
        self._new_inp_filepath = os.path.join(self._cur_dir, new_inp_filename)
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
                        parse_list = line.split(',')
                        node_id = parse_list[0]
                        node_x = float(parse_list[1])
                        node_y = float(parse_list[2])
                        node_z = float(parse_list[3])
                        inst_name = part_name + '-1'
                        disp_data = rst_disp.get((inst_name, node_id), None)
                        if disp_data is None:
                            continue
                        new_node_id = disp_data[0]
                        new_node_x = node_x + disp_data[1]
                        new_node_y = node_y + disp_data[2]
                        new_node_z = node_z + disp_data[3]
                        fp_writer.write('%s,    %f,    %f,    %f' % (new_node_id, new_node_x, new_node_y, new_node_z))
                        fp_writer.write('\n')
                    else:
                        fp_writer.write(line)
                        fp_writer.write('\n')
        print "Finish generating inp file %s " % inp_name


class AbaqusODBModel(object):
    def __init__(self, odb_filepath):
        self._odb_filepath = odb_filepath
        self._odb = None

    def set_up(self):
        from odbAccess import *
        from abaqusConstants import *

        self._odb = openOdb(path=self._odb_filepath, readOnly=False)

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


def get_code_dist_inp_path(inp_filepath):
    inp_model = AbaqusINPModel(inp_filepath)
    inp_model.set_up()
    filename = inp_model.get_filename()
    inp_model.run_inp(inp_name=filename, odb_name=filename)
    odb_filepath = inp_model.get_new_odb_filepath()
    inp_model.generate_inp_from_inst_to_part('blade_code_dist', odb_filepath)
    return inp_model.get_new_inp_filepath()


def get_init_inp_path(inp_filepath):
    inp_model = AbaqusINPModel(inp_filepath)
    inp_model.set_up()
    filename = inp_model.get_filename()
    inp_model.run_inp(inp_name=filename, odb_name=filename)
    odb_filepath = inp_model.get_new_odb_filepath()
    inp_model.generate_inp_from_odb('blade_init', odb_filepath)
    return inp_model.get_new_inp_filepath()


def generate_demo_inp(inp_filepath):
    # inst to node
    clean_inp_filepath = get_code_dist_inp_path(inp_filepath)
    # add disp to demo_inp
    demo_inp = get_init_inp_path(clean_inp_filepath)

    print demo_inp


if __name__ == "__main__":
    inp_filepath = 'D:/SIMULIA/Temp/blade_test.inp'
    # inp_filepath = 'E:/SIMULIA/6.14/Temp/blade_test.inp'
    generate_demo_inp(inp_filepath)




