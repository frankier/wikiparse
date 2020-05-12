import click
from .parse import mod_data_opt


@click.group()
def fst_group():
    pass


@fst_group.command()
@mod_data_opt
@click.argument("outdir", type=click.Path())
def make_fsts(outdir):
    import wikiparse.assoc.fst  # noqa: F401
    from wikiparse.utils.fst import registry

    for fst in registry.values():
        fst.save_fsts(outdir)
