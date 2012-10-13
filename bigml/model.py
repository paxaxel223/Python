# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Copyright 2012 BigML
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""A local Predictive Model.

This module defines a Model to make predictions locally or
embedded into your application without needing to send requests to
BigML.io.

This module cannot only save you a few credits, but also enormously
reduce the latency for each prediction and let you use your models
offline.

You can also visualize your predictive model in IF-THEN rule format
and even generate a python function that implements the model.

Example usage (assuming that you have previously set up the BIGML_USERNAME
and BIGML_API_KEY environment variables and that you own the model/id below):

from bigml.api import BigML
from bigml.model import Model

api = BigML()

model = Model(api.get_model('model/5026965515526876630001b2'))
model.predict({"petal length": 3, "petal width": 1})

You can also see model in a IF-THEN rule format with:

model.rules()

Or auto-generate a python function code for the model with:

model.python()

"""
import logging
LOGGER = logging.getLogger('BigML')

import sys
import operator

from bigml.api import FINISHED
from bigml.util import invert_dictionary, slugify, split, markdown_cleanup, \
    prefix_as_comment, sort_fields

reload(sys)
sys.setdefaultencoding("utf-8")

# Map operator str to its corresponding function
OPERATOR = {
    "<": operator.lt,
    "<=": operator.le,
    "=": operator.eq,
    "!=": operator.ne,
    "/=": operator.ne,
    ">=": operator.ge,
    ">": operator.gt
}

# Map operator str to its corresponding python operator
PYTHON_OPERATOR = {
    "<": "<",
    "<=": "<=",
    "=": "==",
    "!=": "!=",
    "/=": "!=",
    ">=": ">=",
    ">": ">"
}


INDENT = u'    '


class Predicate(object):
    """A predicate to be evaluated in a tree's node.

    """
    def __init__(self, operation, field, value):
        self.operator = operation
        self.field = field
        self.value = value

    def to_rule(self, fields):
        """ Builds rule string from a predicate

        """
        return u"%s %s %s" % (fields[self.field]['name'],
                              self.operator,
                              self.value)


class Tree(object):
    """A tree-like predictive model.

    """
    def __init__(self, tree, fields, objective_field=None):

        self.fields = fields
        if objective_field and isinstance(objective_field, list):
            self.objective_field = objective_field[0]
        else:
            self.objective_field = objective_field

        self.output = tree['output']

        if tree['predicate'] is True:
            self.predicate = True
        else:
            self.predicate = Predicate(
                tree['predicate']['operator'],
                tree['predicate']['field'],
                tree['predicate']['value'])

        children = []
        if 'children' in tree:
            for child in tree['children']:
                children.append(Tree(child, self.fields, objective_field))

        self.children = children
        self.count = tree['count']
        if 'distribution' in tree:
            self.distribution = tree['distribution']
        elif ('objective_summary' in tree):
            summary = tree['objective_summary']
            if 'bins' in summary:
                self.distribution = summary['bins']
            elif 'counts' in summary:
                self.distribution = summary['counts']
            elif 'categories' in summary:
                self.distribution = summary['categories']
        else:
            summary = self.fields[self.objective_field]['summary']
            if 'bins' in summary:
                self.distribution = summary['bins']
            elif 'counts' in summary:
                self.distribution = summary['counts']
            elif 'categories' in summary:
                self.distribution = summary['categories']

    def list_fields(self, out):
        """List a description of the model's fields.

        """
        out.write(u'<%-32s : %s>\n' % (
            self.fields[self.objective_field]['name'],
            self.fields[self.objective_field]['optype']))
        out.flush()

        for field in [(val['name'], val['optype']) for key, val in
                      sort_fields(self.fields)
                      if key != self.objective_field]:
            out.write(u'[%-32s : %s]\n' % (field[0], field[1]))
            out.flush()
        return self.fields

    def predict(self, input_data, path=[]):
        """Makes a prediction based on a number of field values.

        The input fields must be keyed by Id.

        """
        if self.children and split(self.children) in input_data:
            for child in self.children:
                if apply(OPERATOR[child.predicate.operator],
                         [input_data[child.predicate.field],
                         child.predicate.value]):
                    path.append(u"%s %s %s" % (
                                self.fields[child.predicate.field]['name'],
                                child.predicate.operator,
                                child.predicate.value))
                    return child.predict(input_data, path)
        else:
            return self.output, path

    def generate_rules(self, depth=0):
        """Translates a tree model into a set of IF-THEN rules.

        """
        rules = u""
        if self.children:
            for child in self.children:
                rules += (u"%s IF %s %s %s %s\n" %
                         (INDENT * depth,
                          self.fields[child.predicate.field]['slug'],
                          child.predicate.operator,
                          child.predicate.value,
                          "AND" if child.children else "THEN"))
                print rules
                rules += child.generate_rules(depth + 1)
        else:
            rules += (u"%s %s = %s\n" %
                     (INDENT * depth,
                      (self.fields[self.objective_field]['slug']
                       if self.objective_field else "Prediction"),
                      self.output))
        return rules

    def rules(self, out):
        """Prints out an IF-THEN rule version of the tree.

        """
        for field in [(key, val) for key, val in sort_fields(self.fields)]:

            slug = slugify(self.fields[field[0]]['name'])
            self.fields[field[0]].update(slug=slug)
        out.write(self.generate_rules())
        out.flush()

    def python_body(self, depth=1, cmv=False):
        """Translate the model into a set of "if" python statements.

        `depth` controls the size of indentation. If `cmv` (control missing
        values) is set to True then as soon as a value is missing to
        evaluate a predicate the output at that node is returned without
        further evaluation.

        """
        body = u""
        if self.children:
            if cmv:
                field = split(self.children)
                body += (u"%sif (%s is None):\n " %
                        (INDENT * depth,
                         self.fields[field]['slug']))
                if self.fields[self.objective_field]['optype'] == 'numeric':
                    body += (u"%sreturn %s\n" %
                            (INDENT * (depth + 1),
                             self.output))
                else:
                    body += (u"%sreturn '%s'\n" %
                            (INDENT * (depth + 1),
                             self.output))

            for child in self.children:
                body += (u"%sif (%s %s %s):\n" %
                        (INDENT * depth,
                         self.fields[child.predicate.field]['slug'],
                         PYTHON_OPERATOR[child.predicate.operator],
                         repr(child.predicate.value)))
                body += child.python_body(depth + 1)
        else:
            body = u"%sreturn %s\n" % (INDENT * depth, repr(self.output))
        return body

    def python(self, out, docstring):
        """Writes a python function that implements the model.

        """
        args = []

        for field in [(key, val) for key, val in sort_fields(self.fields)]:

            slug = slugify(self.fields[field[0]]['name'])
            self.fields[field[0]].update(slug=slug)
            default = None
            if self.fields[field[0]]['optype'] == 'numeric':
                default = self.fields[field[0]]['summary']['median']
            if field[0] != self.objective_field:
                args.append("%s=%s" % (slug, default))
        predictor_definition = (u"def predict_%s" %
                                self.fields[self.objective_field]['slug'])
        depth = len(predictor_definition) + 1
        predictor = u"%s(%s):\n" % (predictor_definition,
                                   (",\n" + " " * depth).join(args))
        predictor_doc = (INDENT + u"\"\"\" " + docstring +
                         u"\n" + INDENT + u"\"\"\"\n")
        predictor += predictor_doc + self.python_body()
        out.write(predictor)
        out.flush()


class Model(object):
    """ A lightweight wrapper around a Tree model.

    Uses a BigML remote model to build a local version that can be used
    to generate prediction locally.

    """

    def __init__(self, model):

        if (isinstance(model, dict) and 'resource' in model):
            self.resource_id = model['resource']

        if (isinstance(model, dict) and 'object' in model and
                isinstance(model['object'], dict)):
            if ('status' in model['object'] and
                    'code' in model['object']['status']):
                if model['object']['status']['code'] == FINISHED:
                    fields = model['object']['model']['fields']
                    self.inverted_fields = invert_dictionary(fields)
                    self.tree = Tree(
                        model['object']['model']['root'],
                        fields,
                        model['object']['objective_fields'])
                    self.description = model['object']['description']
                else:
                    raise Exception("The model isn't finished yet")
        elif (isinstance(model, dict) and 'model' in model and
                isinstance(model['model'], dict)):
            if ('status' in model and 'code' in model['status']):
                if model['status']['code'] == FINISHED:
                    fields = model['model']['fields']
                    self.inverted_fields = invert_dictionary(fields)
                    self.tree = Tree(
                        model['model']['root'],
                        fields,
                        model['objective_fields'])
                    self.description = model['description']
                else:
                    raise Exception("The model isn't finished yet")
        else:
            raise Exception("Invalid model structure")

    def fields(self, out=sys.stdout):
        """Describes and return the fields for this model.

        """
        self.tree.list_fields(out)

    def predict(self, input_data,
                by_name=True, print_path=False, out=sys.stdout):
        """Makes a prediction based on a number of field values.

        The input fields must be keyed by field name.

        """
        if by_name:
            try:
                input_data = dict(
                    [[self.inverted_fields[key], value]
                        for key, value in input_data.items()])
            except KeyError, field:
                LOGGER.error("Wrong field name %s" % field)
                return

        prediction, path = self.tree.predict(input_data)

        # Prediction path
        if print_path:
            out.write(u' AND '.join(path) + u' => %s \n' % prediction)
            out.flush()
        return prediction

    def rules(self, out=sys.stdout):
        """Returns a IF-THEN rule set that implements the model.

        `out` is file descriptor to write the rules.

        """

        return self.tree.rules(out)

    def python(self, out=sys.stdout):
        """Returns a basic python function that implements the model.

        `out` is file descriptor to write the python code.

        """
        docstring = (u"Predictor for %s from %s\n" % (
            self.tree.fields[self.tree.objective_field]['name'],
            self.resource_id))
        self.description = (unicode(markdown_cleanup(
                self.description).strip())
                or u'Predictive model by BigML - Machine Learning Made Easy' )
        docstring += u"\n" + INDENT * 2 + (u"%s" %
                     prefix_as_comment(INDENT * 2, self.description))
        return self.tree.python(out, docstring)

    def group_prediction(self):
        """ Groups in categories or bins the predicted data

        dict - contains a dict grouping counts in 'total' and 'details' lists.
                'total' key contains a 3-element list.
                       - common segment of the tree for all instances
                       - data count
                       - predictions count
                'details' key contains a list of elements. Each element is a
                          2-element list:
                       - complete path of the tree from the root to the leaf
                       - leaf predictions count
        """
        groups = {}
        tree = self.tree
        distribution = tree.distribution

        for group in distribution:
            groups[group[0]] = {'total': [[], group[1], 0],
                                'details': []}
        path = []

        def depth_first_search(tree, path):
            """ Search for leafs' values and instances
            """
            if isinstance(tree.predicate, Predicate):
                path.append(tree.predicate)

            if len(tree.children) == 0:
                group = tree.output
                if not tree.output in groups:
                    groups[group] = {'total': [[], 0, 0],
                                     'details': []}
                groups[group]['details'].append([path, tree.count])
                groups[group]['total'][2] += tree.count
                return

            children = tree.children[:]
            children.reverse()

            for child in children:
                depth_first_search(child, path[:])

        depth_first_search(tree, path)

        return groups

    def get_data_distribution(self):
        """ Returns training data distribution

        """
        tree = self.tree
        distribution = tree.distribution

        return sorted(distribution,  key=lambda x: x[0])

    def get_prediction_distribution(self, groups=None):
        """ Returns model predicted distribution

        """
        if groups is None:
            groups = self.group_prediction()

        predictions = [[group, groups[group]['total'][2]] for group in groups]
        # remove groups that are not predicted
        predictions = filter(lambda x: x[1] > 0, predictions)

        return sorted(predictions,  key=lambda x: x[0])

    def summarize(self, out=sys.stdout):
        """ Prints summary grouping distribution as class header and details

        """
        def print_distribution(distribution, out=sys.stdout):
            """ Prints distribution data

            """
            total = reduce(lambda x, y: x + y,
                           [group[1] for group in distribution])
            for group in distribution:
                out.write(u"    %s: %.2f%% (%d instance%s)\n" % (group[0],
                          round(group[1] * 1.0 / total, 4) * 100,
                          group[1],
                          "" if group[1] == 1 else "s"))

        def extract_common_path(groups):
            """ Extracts the common segment of the prediction path for a group

            """
            for group in groups:
                details = groups[group]['details']
                common_path = []
                if len(details) > 0:
                    mcd_len = min([len(x[0]) for x in details])
                    for i in range(0, mcd_len):
                        test_common_path = details[0][0][i]
                        for subgroup in details:
                            if subgroup[0][i] != test_common_path:
                                i = mcd_len
                                break
                        if i < mcd_len:
                            common_path.append(test_common_path)
                groups[group]['total'][0] = common_path
                if len(details) > 0:
                    groups[group]['details'] = sorted(details,
                                                      key=lambda x: x[1],
                                                      reverse=True)

        tree = self.tree
        distribution = self.get_data_distribution()

        out.write(u"Data distribution:\n")
        print_distribution(distribution, out=out)
        out.write(u"\n\n")

        groups = self.group_prediction()
        predictions = self.get_prediction_distribution(groups)

        out.write(u"Predicted distribution:\n")
        print_distribution(predictions, out=out)
        out.write(u"\n\n")

        extract_common_path(groups)

        for group in [x[0] for x in predictions]:
            details = groups[group]['details']
            path = [prediction.to_rule(tree.fields) for
                    prediction in groups[group]['total'][0]]
            data_per_group = groups[group]['total'][1] * 1.0 / tree.count
            pred_per_group = groups[group]['total'][2] * 1.0 / tree.count
            out.write(u"\n\n%s : (data %.2f%% / prediction %.2f%%) %s\n" %
                      (group,
                       round(data_per_group, 4) * 100,
                       round(pred_per_group, 4) * 100,
                       " and ".join(path)))

            if len(details) == 0:
                out.write(u"    The model will never predict this class\n")
            for j in range(0, len(details)):
                subgroup = details[j]
                pred_per_sgroup = subgroup[1] * 1.0 / groups[group]['total'][2]
                path = [prediction.to_rule(tree.fields) for
                        prediction in subgroup[0]]
                out.write(u"    · %.2f%%: %s\n" %
                          (round(pred_per_sgroup, 4) * 100,
                          " and ".join(path)))
        out.flush()
