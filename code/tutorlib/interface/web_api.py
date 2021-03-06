import base64
import json
import urllib.parse
import webbrowser

from tutorlib.online.exceptions import AuthError, RequestError, NullResponse
from tutorlib.online.session import SessionManager
from tutorlib.utils.tmp import retrieve


HELP_URL = 'http://csse1001.uqcloud.net/mpt3/help'
VISUALISER_URL \
    = 'http://pythontutor.com/visualize.html'


class WebAPIError(Exception):
    """
    A wrapper class for all exceptions which occur in web communication.

    Attributes:
      message (str): A high-level user-friendly description of the error which
          was encountered.
      details (str): The details of the error, built from the underlying
          exception.

    """
    def __init__(self, message, details=None):
        """
        Initialise a new WebAPIError object.

        Attributes:
          message (str): A high-level user-friendly description of the error
              which was encountered.
          details (str, optional): The details of the error, built from the
              underlying exception.  Defaults to None, which indicates that
              there was no (useful) underlying exception.

        """
        self.message = message
        self.details = details


class WebAPI():
    """
    Interface to the MyPyTutor website.  Encapsulates all online functionality
    on the client side.

    Class Attributes:
      OK (constant): The server response was ok.
      LATE (constant): The server indicated that the given action or request
          was completed successfully, but that the provided data was late.
          This is used in submission-related contexts.
      LATE_OK (constant): The server indicated that the action or request was
          late, but the user has been permitted to complete this action late.
      MISSING (constant): The relevant submission is missing.

    Attributes:
      session_manager (SessionManager): The underlying session manager.

    """
    OK = 'OK'
    LATE = 'LATE'
    LATE_OK = 'LATE_OK'
    MISSING = 'MISSING'

    RESPONSES = {OK, LATE, LATE_OK, MISSING}

    def __init__(self, listener=None):
        """
        Initialise a new WebAPI object.

        It is unlikely that an application would wish to construct more than
        one WebAPI, but this is not prohibited.

        """
        self.session_manager = SessionManager()
        self.listener = listener if listener is not None else lambda _: None

    @property
    def is_logged_in(self):
        """
        Return whether the user is currently logged in.

        """
        return self.session_manager.is_logged_in()

    @property
    def user(self):
        """
        Return the current user.

        If no user is logged in, return None.  Do not attempt to login.

        """
        if not self.is_logged_in:
            return None

        user_info = self.session_manager.user_info()
        return user_info['user']

    def login(self, username=None, password=None):
        """
        Prompt the user to login, if necessary.

        If the user is already logged in, no action will be taken.

        Args:
          username (str, optional): The username to login with.
          password (str, optional): The password to login with.

        Returns:
          Whether the user could be successfully logged in.
          If the user was already logged in, return True.

        """
        if self.is_logged_in:
            return True

        # the SessionManager will keep trying until it is successful
        try:
            success = self.session_manager.login(username, password)
        except Exception as e:
            raise WebAPIError(
                message='Login Failed',
                details=str(e),
            ) from e

        self.listener(success)

        return success

    def logout(self):
        """
        Log out the current user.

        If no user is logged in, do nothing.

        """
        if self.is_logged_in:
            try:
                self.session_manager.logout()
                self.listener(False)
            except Exception as e:
                raise WebAPIError(
                    message='Logout Failed',
                    details=str(e),
                ) from e

    # visualiser
    def visualise(self, code_text):
        """
        Open the given code in the online visualiser.

        This method will launch the default browser, with the code preloaded.

        """
        # format is url (percent) encoded, except spaces are replaced by +
        encoded_text = urllib.parse.quote(code_text, ' ').replace(' ', '+')
        url = VISUALISER_URL.format(code=encoded_text)

        # just open it in the browser
        webbrowser.open(url)

    def display_help(self):
        """
        Open the help webpage.

        This method will launch in the default browser.

        """
        webbrowser.open(HELP_URL)

    # general web communications
    def _request(self, f, values, require_login=True):
        """
        Base method for making a web request.

        If the user is not logged in, they will be prompted to do so.

        Args:
          f ((dict) -> object): The function to call to make the request.
              Will usally be WebAPI._get or WebAPI._post.
          values (dict): The dictionary to pass to the request method.
              Must be in a format compatible with that method.
          require_login (bool, optional): Whether to require the user to log in
              before proceeding with the request.

        Returns:
          The result of running the given request function, if successful.
          If NullResponse is raised, return None.

        Raises:
          WebAPIError: If an AuthError or RequestError is encountered.

        """
        if require_login and not self.login():
            raise WebAPIError(
                message='Authentication Error',
                details='You must be logged in to use this feature',
            )

        try:
            return f(values)
        except AuthError as e:
            raise WebAPIError(
                message='Authentication Failure',
                details=str(e),
            ) from e
        except RequestError as e:
            raise WebAPIError(
                message='Could Not Complete Request',
                details=str(e),
            ) from e
        except NullResponse as e:
            return None

    def _get(self, values, require_login=True):
        """
        Make a get request using the session manager.

        If the user is not logged in, they will be prompted to do so.

        Args:
          values (dict): The data dictionary to pass to the session manager
              get method.
          require_login (bool, optional): Whether to require the user to log in
              before proceeding with the request.

        Returns:
          The result of calling the session manager get method.
          If NullResponse is raised, return None.

        Raises:
          WebAPIError: If an AuthError or RequestError is encountered.

        """
        return self._request(
            self.session_manager.get, values, require_login=require_login
        )

    def _post(self, values, require_login=True):
        """
        Make a post request using the session manager.

        If the user is not logged in, they will be prompted to do so.

        Args:
          values (dict): The data dictionary to pass to the session manager
              post method.
          require_login (bool, optional): Whether to require the user to log in
              before proceeding with the request.

        Returns:
          The result of calling the session manager post method.
          If NullResponse is raised, return None.

        Raises:
          WebAPIError: If an AuthError or RequestError is encountered.

        """
        return self._request(
            self.session_manager.post, values, require_login=require_login
        )

    def _download(self, url, filename=None):
        """
        Download the object at the given URL to the given filename.

        Args:
          url (str): The url to download.
          filename (str, optional): The filename to download to.  Defaults to
              None, which instructs the urlobj library to select a filename.

        Returns:
          The filename the file was downloaded to.
          If the filename keyword argument was provied, this will be that arg.

        Raises:
          WebAPIError: If any exception is encountered in the download process.

        """
        try:
            filename = retrieve(url, filename=filename)
            return filename
        except Exception as e:
            raise WebAPIError(
                message='Could Not Download File',
                details=str(e),
            ) from e

    def get_tutorials_timestamp(self):
        """
        Get the last-modified time of the version of the tutorial package on
        the server.

        Returns:
          The timestamp, as a Unix time.
        """
        values = {
            'action': 'get_tutorials_timestamp'
        }

        result = self._get(values, require_login=False)
        return result.strip()

    def get_tutorials_zipfile(self):
        """
        Download the tutorials zip file from the server.

        Returns:
          The path to the zip file.

        Raises:
          WebAPIError: If any exception is encountered in the download process.

        """
        values = {
            'action': 'get_tut_zip_file',
        }

        result = self._get(values, require_login=False)
        return self._download(result.strip())

    def get_mpt_zipfile(self):
        """
        Download the MyPyTutor Python 3.5 zip file from the server.

        Returns:
          The path to the zip file.

        Raises:
          WebAPIError: If any exception is encountered in the download process.

        """
        values = {
            'action': 'get_mpt',
        }

        result = self._get(values, require_login=False)
        return self._download(result.strip())

    def get_version(self):
        """
        Get the latest MyPyTutor version.

        Returns:
          The latest MyPyTutor version, as a string.

          MyPyTutor versions use the standard three number format
          (basically, major.minor.bugfix).

        """
        values = {
            'action': 'get_version',
        }
        return self._get(values, require_login=False)

    def upload_answer(self, tutorial, problem_set, tutorial_package, code):
        """
        Upload the given code as the student's answer for the given tutorial
        to the server.

        Args:
          tutorial (Tutorial): The tutorial problem to upload the answer for.
          problem_set (ProblemSet): The problem set which contains the
              tutorial to upload the answer for.
          tutorial_package (TutorialPackage): The tutorial package which
              contains the problem set to upload the answer for.
          code (str): The code to upload as the answer.

        Returns:
          Whether the upload was successful (as a bool).

        Raises:
          WebAPIError: If the uploaded code was rejected (eg, because it was
              too long for the server to accept).

        """
        values = {
            'action': 'upload',
            'code': code,
            'tutorial_package_name': tutorial_package.name,
            'problem_set_name': problem_set.name,
            'tutorial_name': tutorial.name,
        }

        result = self._post(values)
        return result.startswith(WebAPI.OK)

    def download_answer(self, tutorial, problem_set, tutorial_package):
        """
        Download the code on the server for the given tutorial.

        Args:
          tutorial (Tutorial): The tutorial problem to download the answer for.
          problem_set (ProblemSet): The problem set which contains the
              tutorial to download the answer for.
          tutorial_package (TutorialPackage): The tutorial package which
              contains the problem set to download the answer for.

        Returns:
          The student's code on the server for the given tutorial.
          None if no code exists for the given tutorial.

        """
        values = {
            'action': 'download',
            'tutorial_package_name': tutorial_package.name,
            'problem_set_name': problem_set.name,
            'tutorial_name': tutorial.name,
        }
        return self._get(values)

    def answer_info(self, tutorial, problem_set, tutorial_package):
        """
        Return information on the server copy of the student's answer for the
        given tutorial.

        Args:
          tutorial (Tutorial): The tutorial problem to get the info for.
          problem_set (ProblemSet): The problem set which contains the
              tutorial to get the info for.
          tutorial_package (TutorialPackage): The tutorial package which
              contains the problem set to get the info for.

        Returns:
          A two-element tuple.

          The first element of the tuple is the sha512 hash of the server copy
          of the student's answer (as a str, not bytes).

          The second element of the tuple is the last-modified tiem of the
          server copy of the student's answer, as a unix timestamp (float).

          If there is no such answer on the server, None will be returned for
          both elements of the tuple.

        Raises:
          WebAPIError: If the response is not valid JSON, or if the 'hash' or
              'timestamp' keys are missing on the response dictionary.

        """
        values = {
            'action': 'answer_info',
            'tutorial_package_name': tutorial_package.name,
            'problem_set_name': problem_set.name,
            'tutorial_name': tutorial.name,
        }
        response = self._get(values)
        if response is None:
            return None, None

        try:
            d = json.loads(response)
        except ValueError:
            raise WebAPIError(
                message='Invalid Response',
                details='Could not decode response: {}'.format(response),
            )  # do not explicitly chain -- not independently useful to caller

        if 'hash' not in d or 'timestamp' not in d:
            raise WebAPIError(
                message='Invalid Response',
                details='Missing keys on response: {}'.format(response),
            )  # do not explicitly chain -- not independently useful to caller

        answer_hash = base64.b32decode(d['hash'])
        timestamp = d['timestamp']

        return answer_hash, timestamp

    def submit_answer(self, tutorial, code, num_attempts):
        """
        Submit the given code as the student's answer for the given tutorial.

        Args:
          tutorial (Tutorial): The tutorial to submit the answer for.
          code (str): The code to submit as the student's answer.
          num_attempts (int): The number of attempts made before successful
            submission.

        Returns:
          True if the answer was submitted on time.
          False if the answer was submitted late.
          None if the answer for this tutorial has already been submitted.

        Raises:
          WebAPIError: If the tutorial is not recognised by the server, or
              if the server response is not one of 'OK' or 'LATE'.

        """
        tutorial_hash = base64.b32encode(tutorial.hash)

        values = {
            'action': 'submit',
            'tutorial_hash': tutorial_hash,
            'num_attempts': num_attempts,
            'code': code,
        }
        response = self._post(values)
        if response is None:
            return None

        response = response.strip()
        if response not in (WebAPI.OK, WebAPI.LATE, WebAPI.LATE_OK):
            raise WebAPIError(
                message='Invalid Response',
                details='Unexpected response: {}'.format(response),
            )

        return response

    def reset_answers(self, tutorials):
        """
        Resets submissions for each given tutorial on the server.

        :param tutorials: The tutorials to reset.
        :return:
        """

        hashes = [base64.b32encode(tutorial.hash) for tutorial in tutorials]
        hashes = ",".join([hash.decode("utf-8") for hash in hashes])

        values = {
            'action': 'reset_submissions',
            'hashes': hashes
        }

        response = self._post(values)
        if response is None:
            return None

    def get_submissions(self, tutorial_package):
        """
        Get information on the student's submissions.

        Only submissions matching the given tutorial package will be returned.
        This allows multiple concurrent tutorial packages to be supported for
        the same student on the same server.

        If the local tutorial package is not up to date, then it is possible
        that actual submissions will not be returned (as the server will always
        return the latest hash).

        Args:
          tutorial_package (TutorialPackage): The tutorial package to return
              submissions for.

        Returns:
          As for _parse_submissions.

        Raises:
          As for _parse_submissions.

        """
        values = {
            'action': 'get_submissions',
        }
        response = self._get(values)

        return self._parse_submissions(response, tutorial_package)

    def _parse_submissions(self, response, tutorial_package):
        """
        Parse a user's submissions from the given response.

        Args:
          response (str): The JSON response to parse the submissions from.
          tutorial_package (TutorialPackage): The tutorial package to return
              submissions for.

        Returns:
          A dictionary containing the submission status of each tutorial.

          The keys of the dictionary will be Tutorial objects (from the given
          tutorial package).

          The corresponding values will be the submission status for that
          tutorial: one of the elements of WebAPI.RESPONSES.

        Raises:
          WebAPIError: If the response is not valid JSON, or if one of the
              elements of the response contains an unknown status.

        """
        # parse our response
        try:
            results = json.loads(response)
        except ValueError:
            raise WebAPIError(
                message='Invalid Response',
                details='Could not decode response: {}'.format(response),
            )  # do not explicitly chain -- not independently useful to caller

        # check that our results are valid, while building our output dict
        output = {}

        for b32_hash, status in results:
            if status not in WebAPI.RESPONSES:
                raise WebAPIError(
                    message='Invalid Response',
                    details='Unknown submission status: {}'.format(status),
                )

            tutorial_hash = base64.b32decode(b32_hash)
            tutorial = tutorial_package.tutorial_with_hash(tutorial_hash)
            if tutorial is None:
                continue  # not on this package; ignore

            output[tutorial] = status

        return output

    def provide_feedback(self, subject, feedback, code=''):
        """
        Provide feedback on MyPyTutor.

        Args:
          subject (str): The subject of the feedback.
          feedback (str): The feedback message itself.
          code (str, optional): The code the user was working on.

        """
        values = {
            'action': 'provide_feedback',
            'subject': subject,
            'feedback': feedback,
            'code': code,
        }
        _ = self._get(values)

    # the following calls require admin access
    def get_student_results(self, user, tutorial_package):
        """
        Get the results for the given student.

        The logged-in user must be a MyPyTutor admin.

        Args:
          user (str): The user to get the results for.
          tutorial_package (TutorialPackage): The tutorial package to get the
              student's results for.

        Returns:
          As for _parse_submissions.

        Raises:
          As for _parse_submissions.

        """
        values = {
            'action': 'get_student_results',
            'user': user,
        }
        response = self._get(values)

        return self._parse_submissions(response, tutorial_package)
