# coding=utf-8
#        BiSon
"""
Implements the ShARC dataset (https://sharc-data.github.io).
"""

import logging
import os
import json
from collections import Counter

from bison.util import write_list_to_file, write_json_to_file
from bison.evals.evaluator_sharc import evaluate as evaluate_sharc
from .dataset_bitext import BitextHandler, GenExample

LOGGER = logging.getLogger(__name__)


class SharcHandler(BitextHandler):
    """
    Handles the ShARC dataset (https://sharc-data.github.io).
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        super().__init__()
        self.examples = []
        self.features = []
        self.write_predictions = write_json_to_file
        self.write_eval = write_json_to_file

    @staticmethod
    def extract_answer(in_file, out_file):
        """
        Given a Sharc json file, extract just the answers
        :param in_file: Sharc json file
        :param out_file: file with just answers
        :return: 0 on success
        """
        with open(in_file, 'r') as file:
            all_elements = json.load(file)
        new_list = []

        for ele in all_elements:
            new_list.append(ele["answer"].replace("\n", " "))

        write_list_to_file(new_list, out_file)
        return 0

    def read_examples(self, input_file, is_training=False):
        """
        Reads a Sharc dataset, each instance in self.examples holds a :py:class:SharcExample object
        :param input_file: the file containing Sharc data (json)
        :param is_training: True for training, then we read in gold labels, else we do not.
        :return: 0 on success
        """
        self.examples = []  # reset previous lot
        LOGGER.info("Part a: question + ruletext + scenario + history")
        LOGGER.info("Part b: answer")
        with open(input_file, "r", encoding='utf-8') as reader:
            all_data = json.load(reader)

        example_counter = 0
        for instance in all_data:

            answer_text = ""
            if is_training is True:
                answer_text = instance["answer"]

            history = []
            for previous_utt in instance["history"]:
                if "follow_up_question" in previous_utt and "follow_up_answer" in previous_utt:
                    history.append([previous_utt["follow_up_question"],
                                    previous_utt["follow_up_answer"]])
                else:
                    logging.info("Warning: key error in: %s", previous_utt)
            evidence = []
            for previous_utt in instance["evidence"]:
                if "follow_up_question" in previous_utt and "follow_up_answer" in previous_utt:
                    evidence.append([previous_utt["follow_up_question"],
                                     previous_utt["follow_up_answer"]])
                else:
                    logging.info("Warning: key error in: %s", previous_utt)

            example = SharcHandler.SharcExample(
                example_index=example_counter,
                utt_id=instance["utterance_id"],
                tree_id=instance["tree_id"],
                source_url=instance["source_url"],
                ruletext=instance["snippet"],
                question_text=instance["question"],
                scenario=instance["scenario"],
                answer_text=answer_text,
                history=history,
                evidence=evidence)
            self.examples.append(example)
            example_counter += 1
        return 0

    def arrange_generated_output(self, current_example, generated_text):
        """
        Reproduces the json output structure that the sharc evaluator expects
        :param current_example: The current example (so that necessary components for writing
        can be accessed, e.g. unique id)
        :param generated_text: the text generated by the model
        :return: a json object
        """
        return {"utterance_id": current_example.utt_id, "answer": generated_text}

    def arrange_token_classify_output(self, current_example, classification_tokens,
                                      input_ids, tokenizer):
        """
        Simply returns all classification elements, other data sets can arrange the output
        as needed here.
        :param current_example: The current example
        :param classification_tokens: the classification labels for all tokens
        :return: classification_tokens in a dictionary so we get json
        """
        return classification_tokens

    def evaluate(self, output_prediction_file, valid_gold, mode='generation'):
        """
        Given the location of the prediction and gold output file,
        calls a dataset specific evaluation script.
        Here calls the Sharc evaluation script.
        :param output_prediction_file: the file location of the predictions
        :param valid_gold: the file location of the gold outputs
        :param mode: if generation, calls combined evaluation
        :return: a dictionary, for classify it has the keys micro_accuracy and macro_accuracy
                for combined additionally bleu_* where * in {1,2,3,4}
        """
        sharc_mode = 'combined'
        self.extract_answer(output_prediction_file, output_prediction_file+".txt")
        self.extract_answer(valid_gold, output_prediction_file+".gold")
        bitext_results = super(SharcHandler, self).evaluate(
            output_prediction_file+".txt", output_prediction_file+".gold", mode=mode)
        os.remove(output_prediction_file+".gold")
        try:
            results = evaluate_sharc(valid_gold, output_prediction_file, sharc_mode)
        except ZeroDivisionError:  # if results are really bad, the evaluate script throws an error
            results = {'micro_accuracy': 0.0, 'macro_accuracy': 0.0, 'bleu_1': 0.0, 'bleu_2': 0.0,
                       'bleu_3': 0.0, 'bleu_4': 0.0}
        for key in results:
            bitext_results[mode+"_"+key] = results[key]
        return bitext_results

    def select_deciding_score(self, results):
        """
        Select the deciding score for saving models.
        :param results: the dictionary returned by the evaluate call
        :return: bleu_4
        """
        deciding_score = results['generation_bleu_4']
        return deciding_score

    class SharcExample(GenExample):
        """A single training/test example from the Sharc corpus.
        """
        # pylint: disable=too-many-arguments
        def __init__(self,
                     example_index,
                     utt_id,
                     tree_id,
                     source_url,
                     ruletext,
                     question_text,
                     scenario,
                     answer_text,
                     history,  # a list of lists where each instance is another list with two items
                     # [follow_up_question, follow_up_answer]
                     evidence):  # evidence has same structure as history
            super().__init__()
            self.example_index = example_index
            self.utt_id = utt_id
            self.tree_id = tree_id
            self.source_url = source_url
            self.ruletext = ruletext
            self.question_text = question_text
            self.scenario = scenario
            self.answer_text = answer_text
            self.history = history
            self.evidence = evidence

            self.part_b = self.answer_text
            self.part_a = ""
            self.part_a += self.question_text + "\n"
            self.part_a += self.ruletext + "\n" + self.scenario
            if history:
                self.part_a += "\n"
            for element in history:
                self.part_a += element[0] + "\n" + element[1] + "\n"
