import time
import json
from datetime import datetime, timedelta
from world import world, res_filename
from bigml.api import HTTP_CREATED
from bigml.api import HTTP_OK
from bigml.api import HTTP_ACCEPTED
from bigml.api import FINISHED
from bigml.api import FAULTY
from bigml.api import get_status

import read_dataset_steps as read

#@step(r'I create a dataset$')
def i_create_a_dataset(step):
    resource = world.api.create_dataset(world.source['resource'])
    world.status = resource['code']
    assert world.status == HTTP_CREATED
    world.location = resource['location']
    world.dataset = resource['object']
    world.datasets.append(resource['resource'])


#@step(r'I download the dataset file to "(.*)"$')
def i_export_a_dataset(step, local_file):
    world.api.download_dataset(world.dataset['resource'],
                               filename=res_filename(local_file))


#@step(r'file "(.*)" is like file "(.*)"$')
def files_equal(step, local_file, data):
    contents_local_file = open(res_filename(local_file)).read()
    contents_data = open(res_filename(data)).read()
    assert contents_local_file == contents_data


#@step(r'I create a dataset with "(.*)"')
def i_create_a_dataset_with(step, data="{}"):
    resource = world.api.create_dataset(world.source['resource'],
                                        json.loads(data))
    world.status = resource['code']
    assert world.status == HTTP_CREATED
    world.location = resource['location']
    world.dataset = resource['object']
    world.datasets.append(resource['resource'])


#@step(r'I wait until the dataset status code is either (\d) or (\d) less than (\d+)')
def wait_until_dataset_status_code_is(step, code1, code2, secs):
    start = datetime.utcnow()
    read.i_get_the_dataset(step, world.dataset['resource'])
    status = get_status(world.dataset)
    while (status['code'] != int(code1) and
           status['code'] != int(code2)):
        time.sleep(3)
        assert datetime.utcnow() - start < timedelta(seconds=int(secs))
        read.i_get_the_dataset(step, world.dataset['resource'])
        status = get_status(world.dataset)
    assert status['code'] == int(code1)

#@step(r'I wait until the dataset is ready less than (\d+)')
def the_dataset_is_finished_in_less_than(step, secs):
    wait_until_dataset_status_code_is(step, FINISHED, FAULTY, secs)

#@step(r'I make the dataset public')
def make_the_dataset_public(step):
    resource = world.api.update_dataset(world.dataset['resource'],
                                        {'private': False})
    world.status = resource['code']
    assert world.status == HTTP_ACCEPTED
    world.location = resource['location']
    world.dataset = resource['object']

#@step(r'I get the dataset status using the dataset\'s public url')
def build_local_dataset_from_public_url(step):
    world.dataset = world.api.get_dataset("public/%s" %
                                          world.dataset['resource'])

#@step(r'the dataset\'s status is FINISHED')
def dataset_status_finished(step):
    assert get_status(world.dataset)['code'] == FINISHED

#@step(r'I create a dataset extracting a (.*) sample$')
def i_create_a_split_dataset(step, rate):
    world.origin_dataset = world.dataset
    resource = world.api.create_dataset(world.dataset['resource'],
                                        {'sample_rate': float(rate)})
    world.status = resource['code']
    assert world.status == HTTP_CREATED
    world.location = resource['location']
    world.dataset = resource['object']
    world.datasets.append(resource['resource'])

#@step(r'I compare the datasets\' instances$')
def i_compare_datasets_instances(step):
    world.datasets_instances = (world.dataset['rows'],
                                world.origin_dataset['rows'])

#@step(r'the proportion of instances between datasets is (.*)$')
def proportion_datasets_instances(step, rate):
    if (int(world.datasets_instances[1] * float(rate)) == world.datasets_instances[0]):
        assert True
    else:
        assert False, (
        "Instances in split: %s, expected %s" % (
            world.datasets_instances[0],
            int(world.datasets_instances[1] * float(rate))))

#@step(r'I create a dataset associated to centroid "(.*)"')
def i_create_a_dataset_from_cluster(step, centroid_id):
    resource = world.api.create_dataset(
        world.cluster['resource'],
        args={'centroid': centroid_id})
    world.status = resource['code']
    assert world.status == HTTP_CREATED
    world.location = resource['location']
    world.dataset = resource['object']
    world.datasets.append(resource['resource'])

#@step(r'I create a dataset from the cluster and the centroid$')
def i_create_a_dataset_from_cluster_centroid(step):
    i_create_a_dataset_from_cluster(step, world.centroid['centroid_id'])

#@step(r'the dataset is associated to the centroid "(.*)" of the cluster')
def is_associated_to_centroid_id(step, centroid_id):
    cluster = world.api.get_cluster(world.cluster['resource'])
    world.status = cluster['code']
    assert world.status == HTTP_OK
    assert "dataset/%s" % (
        cluster['object']['cluster_datasets'][
            centroid_id]) == world.dataset['resource']

#@step(r'I check that the dataset is created for the cluster and the centroid$')
def i_check_dataset_from_cluster_centroid(step):
    is_associated_to_centroid_id(step, world.centroid['centroid_id'])
