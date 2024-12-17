from hermes.config.config import (
    AZURE_MODELS,
    OPENAI_MODELS,
    ANTHROPIC_MODELS,
    GOOGLE_MODELS,
    VALIDATE_KEYS,
    VALIDATE_AZURE
)
from hermes.log import logger
from hermes.core.utils.model import ModelUtils


class HermesConfig:
    """Setup to use in production.
    """
    @staticmethod
    def get_supported_models():
        azure_models = AZURE_MODELS
        openai_models = OPENAI_MODELS
        anthropic_models = ANTHROPIC_MODELS
        google_models = GOOGLE_MODELS

        if VALIDATE_KEYS:
            valid_azure = []
            for azure_model in azure_models:
                if not ModelUtils.check_valid_key(model_id=azure_model):
                    logger.warning(f'Azure key is not valid for {azure_model}.')
                else:
                    logger.info(f'Azure key is valid for {azure_model}.')
                    valid_azure.append(azure_model)
            azure_models = valid_azure

            valid_openai = []
            for openai_model in openai_models:
                if not ModelUtils.check_valid_key(model_id=openai_model):
                    logger.warning(f'OpenAI key is not valid for {openai_model}.')
                else:
                    logger.info(f'OpenAI key is valid for {openai_model}.')
                    valid_openai.append(openai_model)
            openai_models = valid_openai

            valid_anthropic = []
            for anthropic_model in anthropic_models:
                if not ModelUtils.check_valid_key(model_id=anthropic_model):
                    logger.warning(
                        f'Anthropic key is not valid for {anthropic_model}.')
                else:
                    logger.info(
                        f'Anthropic key is valid for {anthropic_model}.')
                    valid_anthropic.append(anthropic_model)
            anthropic_models = valid_anthropic

            valid_google = []
            for google_model in google_models:
                if not ModelUtils.check_valid_key(model_id=google_model):
                    logger.warning(f'Google key is not valid for {google_model}.')
                else:
                    logger.info(f'Google key is valid for {google_model}.')
                    valid_google.append(google_model)
            google_models = valid_google

        return {
            'azure': azure_models,
            'openai': openai_models,
            'anthropic': anthropic_models,
            'google': google_models
        }

    @staticmethod
    def get_description_models(validate_azure=VALIDATE_AZURE):
        supported_models = HermesConfig.get_supported_models()

        gpt_35_turbo_azure_id = supported_models['azure'][1]
        if not validate_azure:
            gpt_35_turbo = gpt_35_turbo_azure_id
        else:
            if ModelUtils.check_valid_key(model_id=gpt_35_turbo_azure_id):
                gpt_35_turbo = gpt_35_turbo_azure_id
            else:
                gpt_35_turbo = ModelUtils.azure_to_oai(gpt_35_turbo_azure_id)

        description_models = [
            # GPT-3.5-Turbo
            gpt_35_turbo,
            # Claude 3: Haiku
            supported_models['anthropic'][2],
            # Claude 3.5: Sonnet
            supported_models['anthropic'][3],
            # Gemini 1.0 Pro
            supported_models['google'][0]
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen description models.')
        return description_models

    @staticmethod
    def get_repair_models():
        supported_models = HermesConfig.get_supported_models()
        repair_models = [
            # GPT-4-Turbo
            supported_models['openai'][2],
            # Claude 3: Sonnet
            supported_models['anthropic'][1]
        ]
        for model in repair_models:
            logger.info(f'Added {model} to chosen repair models.')
        return repair_models

    @staticmethod
    def get_review_models(validate_azure=VALIDATE_AZURE):
        supported_models = HermesConfig.get_supported_models()

        gpt_4o_azure_id = supported_models['azure'][0]
        if not validate_azure:
            gpt_4o = gpt_4o_azure_id
        else:
            if ModelUtils.check_valid_key(model_id=gpt_4o_azure_id):
                gpt_4o = gpt_4o_azure_id
            else:
                gpt_4o = ModelUtils.azure_to_oai(gpt_4o_azure_id)

        review_models = [
            # GPT-4o
            gpt_4o,
            # Claude 3.5: Sonnet
            supported_models['anthropic'][3]
        ]
        for model in review_models:
            logger.info(f'Added {model} to chosen review models.')
        return review_models


class AzureTest:
    @staticmethod
    def get_predescription_models():
        supported_models = HermesConfig.get_supported_models()

        gpt_4o_azure_id = supported_models['azure'][0]
        if ModelUtils.check_valid_key(model_id=gpt_4o_azure_id):
            gpt_4o = gpt_4o_azure_id
        else:
            gpt_4o = ModelUtils.azure_to_oai(gpt_4o_azure_id)

        description_models = [
            # GPT-4o
            gpt_4o,
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen pre-description models.')
        return description_models

    @staticmethod
    def get_description_models():
        supported_models = HermesConfig.get_supported_models()

        gpt_4o_azure_id = supported_models['azure'][0]
        if ModelUtils.check_valid_key(model_id=gpt_4o_azure_id):
            gpt_4o = gpt_4o_azure_id
        else:
            gpt_4o = ModelUtils.azure_to_oai(gpt_4o_azure_id)

        description_models = [
            # GPT-4o
            gpt_4o,
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen description models.')
        return description_models

    @staticmethod
    def get_repair_models():
        supported_models = HermesConfig.get_supported_models()
        gpt_4o_azure_id = supported_models['azure'][0]
        if ModelUtils.check_valid_key(model_id=gpt_4o_azure_id):
            gpt_4o = gpt_4o_azure_id
        else:
            gpt_4o = ModelUtils.azure_to_oai(gpt_4o_azure_id)

        repair_models = [
            # GPT-4o
            gpt_4o,
        ]
        for model in repair_models:
            logger.info(f'Added {model} to chosen repair models.')
        return repair_models

    @staticmethod
    def get_review_models():
        supported_models = HermesConfig.get_supported_models()

        gpt_4o_azure_id = supported_models['azure'][0]
        if ModelUtils.check_valid_key(model_id=gpt_4o_azure_id):
            gpt_4o = gpt_4o_azure_id
        else:
            gpt_4o = ModelUtils.azure_to_oai(gpt_4o_azure_id)

        review_models = [
            # GPT-4o
            gpt_4o,
        ]

        for model in review_models:
            logger.info(f'Added {model} to chosen review models.')
        return review_models



class TestConfig:
    """Setup to use when testing Hermes.
    Meant only to verify that something can be generated.
    """
    @staticmethod
    def get_predescription_models():
        supported_models = HermesConfig.get_supported_models()
        description_models = [
            # Claude 3: Haiku
            supported_models['anthropic'][2],
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen pre-description models.')
        return description_models

    @staticmethod
    def get_description_models():
        supported_models = HermesConfig.get_supported_models()
        description_models = [
            # Claude 3: Haiku
            supported_models['anthropic'][2],
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen description models.')
        return description_models

    @staticmethod
    def get_repair_models():
        supported_models = HermesConfig.get_supported_models()
        repair_models = [
            # Claude 3: Haiku
            supported_models['anthropic'][2],
        ]
        for model in repair_models:
            logger.info(f'Added {model} to chosen repair models.')
        return repair_models

    @staticmethod
    def get_review_models():
        supported_models = HermesConfig.get_supported_models()
        review_models = [
            # Claude 3: Haiku
            supported_models['anthropic'][2],
        ]
        for model in review_models:
            logger.info(f'Added {model} to chosen review models.')
        return review_models


class FeedbackConfig:
    """Setup to use for Feedback repair.
    """
    @staticmethod
    def get_predescription_models():
        supported_models = HermesConfig.get_supported_models()
        description_models = [
            # Claude 3: Haiku
            supported_models['anthropic'][2],
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen pre-description models.')
        return description_models

    @staticmethod
    def get_description_models():
        supported_models = HermesConfig.get_supported_models()

        gpt_35_turbo_azure_id = supported_models['azure'][1]
        if ModelUtils.check_valid_key(model_id=gpt_35_turbo_azure_id):
            gpt_35_turbo = gpt_35_turbo_azure_id
        else:
            gpt_35_turbo = ModelUtils.azure_to_oai(gpt_35_turbo_azure_id)

        description_models = [
            # GPT-3.5-Turbo
            gpt_35_turbo,
            # Claude 3: Haiku
            supported_models['anthropic'][2],
            # Claude 3.5: Sonnet
            supported_models['anthropic'][3],
            # Gemini 1.0 Pro
            supported_models['google'][0]
        ]
        for model in description_models:
            logger.info(f'Added {model} to chosen description models.')
        return description_models

    @staticmethod
    def get_repair_models():
        supported_models = HermesConfig.get_supported_models()
        repair_models = [
            # GPT-4-Turbo
            supported_models['openai'][2],
            # Claude 3: Sonnet
            supported_models['anthropic'][1]
        ]
        for model in repair_models:
            logger.info(f'Added {model} to chosen repair models.')
        return repair_models
