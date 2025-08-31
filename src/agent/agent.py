from pydantic import BaseModel
from bua.computers.actions import ActionUnion, CompletionAction, HelpAction, InteractionAction
import logging
from bua.computers.computer import Browser
from bua.computers import Computer
from bua.utils import create_response, show_image, pp, sanitize_message, check_blocklisted_url
import json
from typing import Any, Callable
from halo import Halo


class ActionParse(BaseModel):
    action: ActionUnion


class Agent:
    """
    Sample agent class for interacting with a computer.

    (See simple_cua_loop.py for a minimal example without an agent.)
    """

    def __init__(
        self,
        model="computer-use-preview",
        computer: Computer = None,
        tools: list[dict] = [],
        acknowledge_safety_check_callback: Callable = lambda: False,
    ):
        self.model = model
        self.computer: Computer | Browser = computer
        self.tools = tools
        self.print_steps = True
        self.debug = False
        self.show_images = False
        self.acknowledge_safety_check_callback = acknowledge_safety_check_callback
        self.usages: list[dict[str, Any]] = []

        if computer:
            dimensions = computer.get_dimensions()
            self.tools += [
                {
                    "type": "computer-preview",
                    "display_width": dimensions[0],
                    "display_height": dimensions[1],
                    "environment": computer.get_environment(),
                }
            ]

    def debug_print(self, *args):
        if self.debug:
            pp(*args)

    def handle_item(self, item):
        """Handle an item; may trigger computer action + screenshot."""
        if item["type"] == "message":
            if self.print_steps:
                print(item["content"][0]["text"])

        if item["type"] == "browser_call":
            if not self.model.startswith("bua"):
                raise NotImplementedError("Browser calls require bua model")

            if not isinstance(self.computer, Browser):
                raise NotImplementedError(
                    f"Cannot execute browser calls on computer of type {type(self.computer)}"
                )

            action = item["action"]
            action_model = ActionParse(action=action)

            if isinstance(action_model.action, CompletionAction):
                status_emoji = "✅" if action_model.action.success else "❌"
                print(f"{status_emoji} Step finished: {action_model.action.answer}")
                return [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": action_model.action.answer,
                    }
                ]
            elif isinstance(action_model.action, HelpAction):
                print(f"Requiring more help: {action_model.action.reason}")
                return [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": action_model.action.reason,
                    }
                ]
            elif isinstance(action_model.action, InteractionAction):
                logging.info(f"✅ Step: {action_model.action.execution_message()}")

            with Halo(action_model.action.execution_message()):
                self.computer.execute_action(action_model.action)

            screenshot_base64 = self.computer.screenshot()
            dom = self.computer.dom()

            call_output = {
                "type": "browser_call_output",
                "call_id": item["call_id"],
                "acknowledged_safety_checks": [],
                "output": {
                    "type": "bua_output",
                    "image_url": f"data:image/png;base64,{screenshot_base64}",
                    "dom": dom,
                },
            }

            current_url = self.computer.get_current_url()
            check_blocklisted_url(current_url)
            call_output["output"]["current_url"] = current_url

            return [call_output]

        if item["type"] == "function_call":
            name, args = item["name"], json.loads(item["arguments"])
            if self.print_steps:
                print(f"{name}({args})")

            if hasattr(self.computer, name):
                method = getattr(self.computer, name)
                method(**args)
            return [
                {
                    "type": "function_call_output",
                    "call_id": item["call_id"],
                    "output": "success",
                }
            ]

        if item["type"] == "computer_call":
            if not self.model.startswith("computer-use"):
                raise NotImplementedError("Computer calls require bua model")

            action = item["action"]
            action_type = action["type"]
            action_args = {k: v for k, v in action.items() if k != "type"}

            if self.print_steps:
                print(f"{action_type}({action_args})")

            method = getattr(self.computer, action_type)
            method(**action_args)

            screenshot_base64 = self.computer.screenshot()
            if self.show_images:
                show_image(screenshot_base64)

            pending_checks = item.get("pending_safety_checks", [])
            for check in pending_checks:
                message = check["message"]
                if not self.acknowledge_safety_check_callback(message):
                    raise ValueError(
                        f"Safety check failed: {message}. Cannot continue."
                    )

            call_output = {
                "type": "computer_call_output",
                "call_id": item["call_id"],
                "acknowledged_safety_checks": pending_checks,
                "output": {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{screenshot_base64}",
                },
            }

            if self.computer.get_environment() == "browser":
                current_url = self.computer.get_current_url()
                check_blocklisted_url(current_url)
                call_output["output"]["current_url"] = current_url

            return [call_output]

        return []

    def run_full_turn(self, input_items, print_steps=True, debug=False, show_images=False):
        self.print_steps = print_steps
        self.debug = debug
        self.show_images = show_images
        new_items = []

        while new_items[-1].get("role") != "assistant" if new_items else True:
            self.debug_print([sanitize_message(msg) for msg in input_items + new_items])
            with Halo("Thinking"):
                response = create_response(
                    model=self.model,
                    input=input_items + new_items,
                    tools=self.tools,
                    truncation="auto",
                )
                if self.model.startswith("bua"):
                    self.usages.append(response["usage"])
            self.debug_print(response)

            if "output" not in response and self.debug:
                print(response)
                raise ValueError("No output from model")
            else:
                new_items += response["output"]
                for item in response["output"]:
                    new_items += self.handle_item(item)

        return new_items
