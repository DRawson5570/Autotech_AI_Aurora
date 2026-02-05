import logging
import math
import re
from datetime import datetime
from typing import Optional, Any
import uuid


from open_webui.utils.misc import get_last_user_message, get_messages_content

from open_webui.config import DEFAULT_RAG_TEMPLATE


log = logging.getLogger(__name__)


def get_task_model_id(
    default_model_id: str, task_model: str, task_model_external: str, models
) -> str:
    # Set the task model
    task_model_id = default_model_id
    # Check if the user has a custom task model and use that model
    if models[task_model_id].get("connection_type") == "local":
        if task_model and task_model in models:
            task_model_id = task_model
    else:
        if task_model_external and task_model_external in models:
            task_model_id = task_model_external

    return task_model_id


def prompt_variables_template(template: str, variables: dict[str, str]) -> str:
    for variable, value in variables.items():
        template = template.replace(variable, value)
    return template


def prompt_template(template: str, user: Optional[Any] = None) -> str:
    """
    Replace template variables in a prompt string with user-specific values.
    
    Template variables:
    - {{USER_FIRST_NAME}}: User's first name (extracted from full name)
    - {{USER_NAME}}: User's full name
    - {{CURRENT_DATE}}, {{CURRENT_TIME}}, etc.
    
    Args:
        template: The template string with {{VARIABLE}} placeholders
        user: User object (UserModel, dict, or None). Must have 'name' attribute/key.
    
    Returns:
        Template string with variables replaced.
    """
    import logging
    log = logging.getLogger(__name__)

    USER_VARIABLES = {}
    # Debug: show whether user object is truthy
    # (no-op; logging is used below if template contains user variables)

    if user:
        # Convert UserModel to dict if needed
        user_dict = user
        if hasattr(user, "model_dump"):
            user_dict = user.model_dump()
        
        if isinstance(user_dict, dict):
            user_info = user_dict.get("info", {}) or {}
            birth_date = user_dict.get("date_of_birth")
            age = None

            if birth_date:
                try:
                    # If birth_date is str, convert to datetime
                    if isinstance(birth_date, str):
                        birth_date = datetime.strptime(birth_date, "%Y-%m-%d")

                    today = datetime.now()
                    age = (
                        today.year
                        - birth_date.year
                        - (
                            (today.month, today.day)
                            < (birth_date.month, birth_date.day)
                        )
                    )
                except Exception as e:
                    pass

            # Extract user's name - this is the key part for USER_FIRST_NAME
            full_name = str(user_dict.get("name", "") or "")
            first_name = ""
            if full_name and full_name.strip() and full_name.lower() != "none":
                name_parts = full_name.strip().split()
                if name_parts:
                    first_name = name_parts[0]
            
            USER_VARIABLES = {
                "name": full_name,
                "first_name": first_name,
                "location": str(user_info.get("location") or ""),
                "bio": str(user_dict.get("bio") or ""),
                "gender": str(user_dict.get("gender") or ""),
                "birth_date": str(birth_date or ""),
                "age": str(age or ""),
            }
            
            # Log the user info for debugging (only when template contains user variables)
            if "{{USER_" in template:
                user_id = user_dict.get("id", "unknown")[:8] if user_dict.get("id") else "unknown"
                log.info(f"prompt_template: user_id={user_id}, name_present={'yes' if full_name else 'no'}, first_name='{first_name or '<empty>'}'")
                # Specifically log when USER_FIRST_NAME is present so we can trace inconsistencies
                if "{{USER_FIRST_NAME}}" in template:
                    log.info(f"prompt_template_applied: user={user_id}, first_name='{first_name or '<empty>'}'")

    # Get the current date
    current_date = datetime.now()

    # Format the date to YYYY-MM-DD
    formatted_date = current_date.strftime("%Y-%m-%d")
    formatted_time = current_date.strftime("%I:%M:%S %p")
    formatted_weekday = current_date.strftime("%A")

    template = template.replace("{{CURRENT_DATE}}", formatted_date)
    template = template.replace("{{CURRENT_TIME}}", formatted_time)
    template = template.replace(
        "{{CURRENT_DATETIME}}", f"{formatted_date} {formatted_time}"
    )
    template = template.replace("{{CURRENT_WEEKDAY}}", formatted_weekday)

    template = template.replace("{{USER_NAME}}", USER_VARIABLES.get("name", "Unknown"))
    first_name_val = USER_VARIABLES.get("first_name", "")
    template = template.replace("{{USER_FIRST_NAME}}", first_name_val)

    # Cleanup formatting when first name is missing. This avoids outputs like "Hello ! I'm Aurora." and
    # removes spaces before punctuation as well as collapsing multiple spaces.
    if not first_name_val:
        # Remove spaces that appear before punctuation (e.g., "Hello !" -> "Hello!")
        template = re.sub(r"\s+([,!?;:.])", r"\1", template)
        # Collapse multiple spaces
        template = re.sub(r"\s{2,}", " ", template)
        # Cleanup patterns like "Hello!  I'm" -> "Hello! I'm" (already handled above but keep safe)
        template = template.replace("!  ", "! ")

    template = template.replace("{{USER_BIO}}", USER_VARIABLES.get("bio", "Unknown"))
    template = template.replace(
        "{{USER_GENDER}}", USER_VARIABLES.get("gender", "Unknown")
    )
    template = template.replace(
        "{{USER_BIRTH_DATE}}", USER_VARIABLES.get("birth_date", "Unknown")
    )
    template = template.replace(
        "{{USER_AGE}}", str(USER_VARIABLES.get("age", "Unknown"))
    )
    template = template.replace(
        "{{USER_LOCATION}}", USER_VARIABLES.get("location", "Unknown")
    )

    return template


def replace_prompt_variable(template: str, prompt: str) -> str:
    def replacement_function(match):
        full_match = match.group(
            0
        ).lower()  # Normalize to lowercase for consistent handling
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)

        if full_match == "{{prompt}}":
            return prompt
        elif start_length is not None:
            return prompt[: int(start_length)]
        elif end_length is not None:
            return prompt[-int(end_length) :]
        elif middle_length is not None:
            middle_length = int(middle_length)
            if len(prompt) <= middle_length:
                return prompt
            start = prompt[: math.ceil(middle_length / 2)]
            end = prompt[-math.floor(middle_length / 2) :]
            return f"{start}...{end}"
        return ""

    # Updated regex pattern to make it case-insensitive with the `(?i)` flag
    pattern = r"(?i){{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}"
    template = re.sub(pattern, replacement_function, template)
    return template


def replace_messages_variable(
    template: str, messages: Optional[list[dict]] = None
) -> str:
    def replacement_function(match):
        full_match = match.group(0)
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)
        # If messages is None, handle it as an empty list
        if messages is None:
            return ""

        # Process messages based on the number of messages required
        if full_match == "{{MESSAGES}}":
            return get_messages_content(messages)
        elif start_length is not None:
            return get_messages_content(messages[: int(start_length)])
        elif end_length is not None:
            return get_messages_content(messages[-int(end_length) :])
        elif middle_length is not None:
            mid = int(middle_length)

            if len(messages) <= mid:
                return get_messages_content(messages)
            # Handle middle truncation: split to get start and end portions of the messages list
            half = mid // 2
            start_msgs = messages[:half]
            end_msgs = messages[-half:] if mid % 2 == 0 else messages[-(half + 1) :]
            formatted_start = get_messages_content(start_msgs)
            formatted_end = get_messages_content(end_msgs)
            return f"{formatted_start}\n{formatted_end}"
        return ""

    template = re.sub(
        r"{{MESSAGES}}|{{MESSAGES:START:(\d+)}}|{{MESSAGES:END:(\d+)}}|{{MESSAGES:MIDDLETRUNCATE:(\d+)}}",
        replacement_function,
        template,
    )

    return template


# {{prompt:middletruncate:8000}}


def rag_template(template: str, context: str, query: str):
    if template.strip() == "":
        template = DEFAULT_RAG_TEMPLATE

    template = prompt_template(template)

    if "[context]" not in template and "{{CONTEXT}}" not in template:
        log.debug(
            "WARNING: The RAG template does not contain the '[context]' or '{{CONTEXT}}' placeholder."
        )

    if "<context>" in context and "</context>" in context:
        log.debug(
            "WARNING: Potential prompt injection attack: the RAG "
            "context contains '<context>' and '</context>'. This might be "
            "nothing, or the user might be trying to hack something."
        )

    query_placeholders = []
    if "[query]" in context:
        query_placeholder = "{{QUERY" + str(uuid.uuid4()) + "}}"
        template = template.replace("[query]", query_placeholder)
        query_placeholders.append((query_placeholder, "[query]"))

    if "{{QUERY}}" in context:
        query_placeholder = "{{QUERY" + str(uuid.uuid4()) + "}}"
        template = template.replace("{{QUERY}}", query_placeholder)
        query_placeholders.append((query_placeholder, "{{QUERY}}"))

    template = template.replace("[context]", context)
    template = template.replace("{{CONTEXT}}", context)

    template = template.replace("[query]", query)
    template = template.replace("{{QUERY}}", query)

    for query_placeholder, original_placeholder in query_placeholders:
        template = template.replace(query_placeholder, original_placeholder)

    return template


def title_generation_template(
    template: str, messages: list[dict], user: Optional[Any] = None
) -> str:

    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = prompt_template(template, user)

    return template


def follow_up_generation_template(
    template: str, messages: list[dict], user: Optional[Any] = None
) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = prompt_template(template, user)
    return template


def tags_generation_template(
    template: str, messages: list[dict], user: Optional[Any] = None
) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = prompt_template(template, user)
    return template


def image_prompt_generation_template(
    template: str, messages: list[dict], user: Optional[Any] = None
) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = prompt_template(template, user)
    return template


def emoji_generation_template(
    template: str, prompt: str, user: Optional[Any] = None
) -> str:
    template = replace_prompt_variable(template, prompt)
    template = prompt_template(template, user)

    return template


def autocomplete_generation_template(
    template: str,
    prompt: str,
    messages: Optional[list[dict]] = None,
    type: Optional[str] = None,
    user: Optional[Any] = None,
) -> str:
    template = template.replace("{{TYPE}}", type if type else "")
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = prompt_template(template, user)
    return template


def query_generation_template(
    template: str, messages: list[dict], user: Optional[Any] = None
) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)

    template = prompt_template(template, user)
    return template


def moa_response_generation_template(
    template: str, prompt: str, responses: list[str]
) -> str:
    def replacement_function(match):
        full_match = match.group(0)
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)

        if full_match == "{{prompt}}":
            return prompt
        elif start_length is not None:
            return prompt[: int(start_length)]
        elif end_length is not None:
            return prompt[-int(end_length) :]
        elif middle_length is not None:
            middle_length = int(middle_length)
            if len(prompt) <= middle_length:
                return prompt
            start = prompt[: math.ceil(middle_length / 2)]
            end = prompt[-math.floor(middle_length / 2) :]
            return f"{start}...{end}"
        return ""

    template = re.sub(
        r"{{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}",
        replacement_function,
        template,
    )

    responses = [f'"""{response}"""' for response in responses]
    responses = "\n\n".join(responses)

    template = template.replace("{{responses}}", responses)
    return template


def tools_function_calling_generation_template(template: str, tools_specs: str) -> str:
    template = template.replace("{{TOOLS}}", tools_specs)
    return template
