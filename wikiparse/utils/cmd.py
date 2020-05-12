import click


class Mutex(click.Option):
    def __init__(self, *args, **kwargs):
        self.not_required_if: list = kwargs.pop("not_required_if")

        assert self.not_required_if, "'not_required_if' parameter required"
        kwargs["help"] = (
            kwargs.get("help", "")
            + "Option is mutually exclusive with "
            + ", ".join(self.not_required_if)
            + "."
        ).strip()
        super(Mutex, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current_opt: bool = self.consume_value(ctx, opts)
        for other_param in ctx.command.get_params(ctx):
            if other_param is self:
                continue
            if other_param.human_readable_name in self.not_required_if:
                other_opt: bool = other_param.consume_value(ctx, opts)
                if other_opt:
                    if current_opt:
                        raise click.UsageError(
                            "Illegal usage: '"
                            + str(self.name)
                            + "' is mutually exclusive with "
                            + str(other_param.human_readable_name)
                            + "."
                        )
                    else:
                        self.required = None
        return super(Mutex, self).handle_parse_result(ctx, opts, args)
