from torchvision import datasets, transforms

from enb.config import get_options

from enb import ml
import model_Resnet18.model_resnet18

options = get_options(from_main=False)


if __name__ == '__main__':
    models = []
    models.append(model_Resnet18.model_resnet18.Resnet18(10))

    dataset_path = './datasets/'
    test_set = datasets.FashionMNIST("data", train=False, download=True,
                                     transform=transforms.Compose([
                                         transforms.Lambda(lambda image: image.convert('RGB')),
                                         transforms.ToTensor(),
                                         transforms.Resize((224, 224))]))

    exp = ml.MachineLearningExperiment(models=models, dataset_paths=dataset_path, test_set=test_set)

    df = exp.get_df(overwrite=options.force > 0)