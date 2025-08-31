import argparse
from lumiteh.agent.agent import Agent
from lumiteh.computers.config import *
from lumiteh.computers.default import *
from lumiteh.computers import computers_config

from dotenv import load_dotenv

_ = load_dotenv()


def acknowledge_safety_check_callback(message: str) -> bool:
    response = input(
        f"Safety Check Warning: {message}\nDo you want to acknowledge and proceed? (y/n): "
    ).lower()
    return response.lower().strip() == "y"


def main():
    parser = argparse.ArgumentParser(
        description="Select a computer environment from the available options."
    )
    _ = parser.add_argument(
        "--computer",
        choices=computers_config.keys(),
        help="Choose the computer environment to use.",
        default="local-playwright",
    )
    _ = parser.add_argument(
        "--input",
        type=str,
        help="Initial input to use instead of asking the user.",
        default=None,
    )
    _ = parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for detailed output.",
    )
    _ = parser.add_argument(
        "--show",
        action="store_true",
        help="Show images during the execution.",
    )
    _ = parser.add_argument(
        "--start-url",
        type=str,
        help="Start the browsing session with a specific URL (only for browser environments).",
        default="https://bing.com",
    )
    _ = parser.add_argument(
        "--model",
        type=str,
        choices=["lumiteh", "cua"],
        help="The reasoning model to use",
        default="lumiteh",
    )
    args = parser.parse_args()
    ComputerClass = computers_config[args.computer]

    if args.model == "lumiteh":
        model = "lumiteh-v1"
    elif args.model == "cua":
        model = "computer-use-preview"
    else:
        raise ValueError(f"invalid model {args.model}")

    with ComputerClass() as computer:
        agent = Agent(
            computer=computer,
            model=model,
            acknowledge_safety_check_callback=acknowledge_safety_check_callback,
        )
        items = []

        if args.computer in ["browserbase", "local-playwright"]:
            if not args.start_url.startswith("http"):
                args.start_url = "https://" + args.start_url
            agent.computer.goto(args.start_url)

        while True:
            try:
                user_input = args.input or input("> ")
                if user_input == "exit":
                    break
            except EOFError as e:
                print(f"An error occurred: {e}")
                break
            items.append({"role": "user", "content": user_input})
            output_items = agent.run_full_turn(
                items,
                print_steps=True,
                show_images=args.show,
                debug=args.debug,
            )
            items += output_items
            args.input = None


if __name__ == "__main__":
    main()
