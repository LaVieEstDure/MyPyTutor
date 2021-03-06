"""
Attributes:
  STUDENT_LOCALS_NAME (constant): The name of the variable which contains the
      locals dictionary, built from compiling and executing the student code.
      This variable should be treated as being mutable, and so a copy should be
      used if there is any danger of changing its value.
  TEST_RESULT_IDENTIFIER (constant): The name to use for storing the test
      result.  This must not conflict with any name likely to be used by a
      student in their own code.

"""
import copy
import inspect
from io import StringIO
import unittest

from tutorlib.testing.streams \
        import redirect_stdin, redirect_stdout, redirect_stderr, \
        redirect_input_prompt
from tutorlib.testing.support import trim_indentation

STUDENT_LOCALS_NAME = 'student_lcls'
TEST_RESULT_IDENTIFIER = '__test_result'


class StudentTestCase(unittest.TestCase):
    """
    A custom unittest.TestCase subclass for use in MyPyTutor tutorial packages.

    This class provides methods for executing arbitrary code in the same
    context as the student code.

    Attributes:
      standard_output (str): Contains stdout after running a test on the
          student's code.
      error_output (str): Contains stderr after running a test on the
          sttudent's code.

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.standard_output = ''
        self.error_output = ''

    def run_in_student_context(self, f, input_text=''):
        """
        Execute the given function in the context of the student's code, using
        the provided input_text (if any) as stdin.

        Note that name of the given function will be injected into the student
        context, meaning that it should be unique (ie, things will go terribly
        wrong if you give it the same name as a builtin or as a function which
        the student may reasonably have defined).

        Because the source of the function will be run in the student context
        (cf the function itself), the function will not operate as a closure.
        It will therefore not have access to variables defined in any outer
        scope as at the time it was defined.

        This method will update .standard_output and .error_output to be the
        contents of stdout and stderr respectively.

        Args:
          f (() -> object): The function to execute in the student context.
              The source of this function will be compiled and executed in the
              student context.  The function object iself will not be.  As a
              result, it will not operate as a closure.
          input_text (str, optional): The text to pass in as stdin.  Defaults
              to an empty string (ie, no input).

        Returns:
          The result of running the given function in the student context.

        """
        # create streams
        input_stream = StringIO(input_text or '')
        output_stream = StringIO()
        error_stream = StringIO()
        input_prompts_stream = StringIO()

        # we have a function object, f, that we want to execute in a specific
        # context (that of the student's code)
        # ideally, we'd just exec the object with those locals and globals, but
        # there's no built-in support for that in Python (at least that I can
        # find)
        # however, we can easily exec a *string* in a specific context
        # so our 'simple' solution is this: grab the source of the function we
        # want to run and exec *that* in the context of the student code
        assert STUDENT_LOCALS_NAME in globals(), \
                'Could not find {} in globals()'.format(STUDENT_LOCALS_NAME)
        student_lcls = globals()[STUDENT_LOCALS_NAME]
        lcls = copy.copy(student_lcls)

        function_source = trim_indentation(inspect.getsource(f))
        exec(compile(function_source, '<test_function>', 'exec'), lcls)

        # we now have our function, as an object, in the context of the
        # student code
        # now we need to actually *run* it, and extract the output, in that
        # same context, and again we need a string for that
        function_name = f.__name__
        test_statement = '{} = {}()'.format(
            TEST_RESULT_IDENTIFIER, function_name
        )

        # finally, actually execute that test function, and extract the result
        with redirect_stdin(input_stream), redirect_stdout(output_stream), \
                redirect_stderr(error_stream), \
                redirect_input_prompt(lcls, input_prompts_stream):
            exec(compile(test_statement, '<test_run>', 'single'), lcls)
            result = lcls[TEST_RESULT_IDENTIFIER]

        self.standard_output = output_stream.getvalue()
        self.error_output = error_stream.getvalue()
        self.input_prompts = input_prompts_stream.getvalue()

        return result
