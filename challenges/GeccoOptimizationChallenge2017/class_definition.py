from ..base_challenge import CrowdAIBaseChallenge
from ..job_states import JobStates
import random
import requests
import json
import uuid
import redis
import time

class GeccoOptimizationChallenge2017(CrowdAIBaseChallenge):
    def __init__(self, config, REDIS_POOL):
        CrowdAIBaseChallenge.__init__(self, config, REDIS_POOL)
        self.challenge_id = "GeccoOptimizationChallenge2017"
        self.supported_functions = ["evaluate", "submit"]

    def execute_function(self, function_name, data, extra_params, socketio, dry_run=False):
        """
        Request Params:
            session_token : String
                Unique identifier for a particular session
            function_name : String
                Unique identifier for the relevant function in the challenge
            data : JSON Object
                JSON object which needs to be passed onto the said function
            extra_params : Object
                Extra Parameters that the said function might need to process
                the data
                * client_response_channel : String
                    socket.io response channel where the client
                    can be relayed the messages from the JobFactory
            socketio : SocketIO Object
                Holds the current session contexxt
            dry_run : Boolean
                Boolean Variable which states if the operation is needed to be
                actually executed, or randomly generated but semantically relevant
                response is supposed to be returned.

        Response Params:
            status : Boolean
                Holds True if the operation is successfully executed
            message : String
                Holds an optional error message in case of failure of execution
            response: JSON Object
                JSON object which holds the response of the function
        """
        _message = {}
        if function_name not in self.supported_functions:
            _message["status"] = False
            # To-DO: Add localization to string messages
            _message["message"] = "Function `%s`  unrecognized in context of the %s challenge" % (function_name, challenge_id)
            _message["response"] = {}
            return _message
        else:
            redis_conn = redis.Redis(connection_pool = self.redis_pool)
            respond_to_me_at = self.challenge_id+'::enqueue_job_response::'+ str(uuid.uuid4())
            _payload = {
                "respond_to_me_at": respond_to_me_at,
                "function_name": "evaluate", #or can also provide "submit"
                "data" : data
            }
            redis_conn.publish(self.challenge_id+'::enqueue_job', json.dumps(_payload))
            # Refer to the comments in JobFactory (run.py) to understand why we have so many response channels
            # when interacting with the jobfactory
            job_response_channel_name = redis_conn.blpop(respond_to_me_at)

            # Now keep blpop-ing on the job_response_channel_name
            # until either the Job is complete or there is an error
            while True:
                job_response = redis_conn.blpop(job_response_channel_name)
                # The actual response looks like :
                # ('GeccoOptimizationChallenge2017::job_response::d57daf8d-9d96-42ae-ba61-d698f665a753', "{'job_state': 'crowdai.job_state.COMPLETE', 'data': {'score': 45}, 'message': ''}")
                # So we simply ignore the first parameter (the name of job_response_channel_name),
                # and focus on the actual response object
                job_response_blob = json.loads(job_response[1])

                # Relay the response to the client
                socketio.emit(extra_params['client_response_channel'], job_response)
                # Note: time.sleep ensures that the emit message is transferred instantaneously
                # More details : https://github.com/miguelgrinberg/Flask-SocketIO/issues/318
                # If there are performance issues, this can be removed.
                time.sleep(0)
                if job_response_blob['job_state'] == JobStates.COMPLETE:
                    return {}
                if job_response_blob['job_state'] == JobStates.ERROR:
                    return {}
            return {}
